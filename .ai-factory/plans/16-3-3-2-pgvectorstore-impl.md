# Plan: 3.3.2 — PgVectorStore (impl)

## Context
Turn 3.3.1's red `KnowledgeStore` tests green by implementing `PgVectorStore` over the asyncpg pool (atomic delete-then-insert upsert, scoped delete, cosine-ordered query) and extend `Settings` with the Postgres connection params plus a derived DSN.

## Settings
- Testing: no
- Logging: minimal
- Docs: no

## Tasks

### Phase 1: Config

- [x] **Task 1: Add Postgres connection settings + derived DSN**
  Files: `src/core/config.py`
  Extend `Settings` with the Postgres fields, mapped from the existing `POSTGRES_*` env vars (already present in `.env.example`, so no env-file change is needed). **Default all five fields** to the same values `tests/knowledge/conftest.py::_dsn` defaults them to — the conftest defaults every value, not just host/port:
  - `postgres_host: str = "localhost"`
  - `postgres_port: int = 5432`
  - `postgres_user: str = "herald_username"`
  - `postgres_password: str = "herald_password"`
  - `postgres_db: str = "herald_database"`
  All five must stay defaulted (not required). This preserves the codebase's documented `Settings()`-constructible invariant (`src/github/mirror.py` lines 30–32: `Settings`' defaults exist only to keep `Settings()` constructible for the webhook test suite): the webhook/ingestion suites build `Settings()` via `get_settings()` in the request path while `tests/conftest.py` monkeypatches only `GITHUB_WEBHOOK_SECRET`/`SERVE_ALLOWLIST` — making Postgres fields required would break those unrelated suites under a bare `uv run pytest` (no `.env.dev` exported). Do NOT make these fields required; a "fail fast when unconfigured" posture, if ever wanted, follows mirror.py's pattern (keep the default, assert presence at the composition root) rather than coupling every `Settings()` to a live Postgres config.
  Add a derived DSN as a read-only property, e.g. `postgres_dsn`, returning `f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"`. With the defaults above this yields exactly the shape `_dsn()` builds by default, so composition roots can feed `create_pool(settings.postgres_dsn)`. Keep the existing pattern: fields typed, no env read outside `Settings`. Do not add validators or percent-encoding beyond what pydantic-settings provides by default — match the conftest's identical unescaped `_dsn()` shape (production credential hardening is out of scope for this task).

### Phase 2: Store implementation

- [x] **Task 2: Implement `PgVectorStore.upsert` — atomic delete-then-insert** (depends on Task 1)
  Files: `src/knowledge/store.py`
  Replace the `NotImplementedError` body. Acquire a connection from `self._pool` and open a transaction (`async with conn.transaction():`) so the whole replace is all-or-nothing (a crash mid-write leaves the prior chunks intact). Inside the txn:
  - `DELETE FROM chunks WHERE repo = $1 AND path = $2` for `(repo, path)`.
  - Insert each item from `items` with `chunk_index` = its position via `enumerate`, columns `(repo, path, chunk_index, content, embedding)`. Prefer `executemany` (or a single multi-row insert) over per-row awaits. `embedding` marshals through the `vector` codec registered in `src/core/db.py` (pass the raw `list[float]`).
  This makes upsert idempotent — re-upserting the same `(repo, path)` replaces rather than appends, and shrinking the chunk count leaves no stale higher indices (greens `test_upsert_atomically_replaces_prior_chunks_for_the_path`). No version/ordering guard: per the spec, out-of-order same-ref writes are benign and self-healing.

- [x] **Task 3: Implement `PgVectorStore.delete` — path-scoped removal** (depends on Task 1)
  Files: `src/knowledge/store.py`
  `DELETE FROM chunks WHERE repo = $1 AND path = $2`, executed on a pool connection. Scoped strictly to the given `(repo, path)` — no other path or repo is touched (greens `test_delete_removes_only_the_scoped_path`). Reuse this same statement inside Task 2's upsert to avoid duplicating the delete SQL.

- [x] **Task 4: Implement `PgVectorStore.query` — cosine-ordered nearest, optional repo scope** (depends on Task 1)
  Files: `src/knowledge/store.py`
  `SELECT repo, path, chunk_index, content, embedding FROM chunks` ordered by cosine distance to the query embedding using the `<=>` operator (cosine distance — matches the `vector_cosine_ops` HNSW index in `schema.sql`; do NOT use `<->`/`<#>`, which would order by the wrong metric and silently return non-nearest chunks). Append `ORDER BY embedding <=> $N LIMIT $M`. When `repo` is provided, add `WHERE repo = $k` and shift the positional params accordingly; when `repo is None`, omit the WHERE clause (build the SQL/params conditionally). Hydrate each returned row into a `Chunk(content=..., embedding=..., repo=..., path=..., chunk_index=...)` so callers can identify a chunk's source (greens `test_query_orders_results_nearest_first_by_cosine`). Pass the query embedding as a `list[float]`; the registered codec encodes it.

- [x] **Task 5: Preserve the dimension guard — no client-side truncate/pad** (depends on Tasks 2, 4)
  Files: `src/knowledge/store.py`
  Confirm neither upsert nor query resizes, pads, or truncates embeddings before sending them to Postgres — the `list[float]` is passed through as-is. pgvector's `vector(768)` column strictly rejects a wrong-dimension vector on both insert and comparison, so a dim mismatch surfaces as a raised database error rather than a silent truncation, satisfying the guard. This is a review/verification checkpoint over Tasks 2 and 4, not new code: ensure no defensive slicing/padding was introduced.
