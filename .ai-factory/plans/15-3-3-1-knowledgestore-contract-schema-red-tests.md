# Plan: 3.3.1 — KnowledgeStore contract + schema (red tests)

## Context
Lay the persistence pool (`src/core/db.py`), the `chunks` pgvector schema, and the `KnowledgeStore` ABC + raising stub, then pin the store's contract — true cosine-nearest ordering, atomic per-`(repo,path)` replace, path-scoped delete — with red tests against a dev pgvector. This is the seam-and-schema half; 3.3.2 turns the tests green.

## Settings
- Testing: no
- Logging: minimal
- Docs: no

## Tasks

### Phase 1: Dependencies & the asyncpg pool

- [x] **Task 1: Add asyncpg + async test dependencies**
  Files: `pyproject.toml`
  Add `asyncpg` to `[project].dependencies`. Add `pytest-asyncio` to the `dev` dependency group. Under `[tool.pytest.ini_options]` add `asyncio_mode = "auto"` so `async def test_...` functions run without a per-test marker (keep the existing `testpaths`/`pythonpath`). Run `uv sync` so the lockfile/venv pick up the new packages. Do NOT add a `pgvector`/`numpy` package — the pool registers a manual `vector` codec (Task 2) to keep embeddings as plain `list[float]`.

- [x] **Task 2: asyncpg pool factory with a vector codec** (depends on Task 1)
  Files: `src/core/db.py` (new)
  Add an async factory `create_pool(dsn: str) -> asyncpg.Pool` that opens an `asyncpg` connection pool from a DSN. Give the pool an `init` connection callback that registers a text type codec for the pgvector `vector` type via `conn.set_type_codec("vector", schema="public", encoder=..., decoder=..., format="text")`: the encoder renders a `list[float]` as pgvector's text form `"[1.0,2.0,3.0]"`; the decoder parses that text back into a `list[float]`. This lets `KnowledgeStore` marshal `embedding: list[float]` directly (and is why the ABC in Task 4 names no pgvector concept). `src/core/db.py` is cross-cutting infra (like `config.py`) — it is the ONLY module that knows Postgres/pgvector here; features depend on the `KnowledgeStore` abstraction, never on this file. This module is written once here and is not edited by 3.3.2, so the codec must be complete now.

### Phase 2: Schema & the KnowledgeStore contract

- [x] **Task 3: chunks schema DDL** (depends on none)
  Files: `src/knowledge/__init__.py` (new, empty package marker), `src/knowledge/schema.sql` (new)
  Write idempotent DDL:
  - `CREATE EXTENSION IF NOT EXISTS vector;`
  - `CREATE TABLE IF NOT EXISTS chunks` with columns `repo text NOT NULL`, `path text NOT NULL`, `chunk_index int NOT NULL`, `content text NOT NULL`, `embedding vector(768) NOT NULL`, and `PRIMARY KEY (repo, path, chunk_index)`. The PK is what structurally forbids a duplicate `chunk_index` within a `(repo, path)`.
  - an ANN cosine index: `CREATE INDEX IF NOT EXISTS chunks_embedding_cos_idx ON chunks USING hnsw (embedding vector_cosine_ops);`
  The `768` dimension matches `Settings.embed_model` (`nomic-embed-text`, 768-dim) from 3.2. Keep the file plain SQL (no plan/roadmap references in comments).

- [x] **Task 4: Chunk value object + KnowledgeStore ABC + raising stub** (depends on Task 2, Task 3)
  Files: `src/knowledge/store.py` (new)
  Define, following the `Embedder`/`LLMClient` ABC pattern in `src/llm/`:
  - `Chunk` — a frozen dataclass value object: `content: str`, `embedding: list[float]`, and query-hydration fields `repo: str | None = None`, `path: str | None = None`, `chunk_index: int | None = None`. On upsert the `(repo, path)` come from the method args and `chunk_index` is the item's position; on query results these are populated so a caller (the reasoner, cross-project) can identify a chunk's source.
  - `KnowledgeStore(ABC)` with three abstract async methods, naming **no** pgvector/Postgres concept:
    - `async def upsert(self, repo: str, path: str, items: list[Chunk]) -> None`
    - `async def delete(self, repo: str, path: str) -> None`
    - `async def query(self, embedding: list[float], k: int, repo: str | None = None) -> list[Chunk]`
  - `PgVectorStore(KnowledgeStore)` — the STUB: `__init__(self, pool)` stores the asyncpg pool; every method raises `NotImplementedError`. 3.3.2 replaces these bodies in this same file (delete-then-insert txn for `upsert`, cosine `ORDER BY` for `query`) — the class name and constructor stay stable so the tests move from red to green unchanged.
  Docstring notes the contract each method must honour (cosine-nearest ordering, atomic replace, scoped delete) so 3.3.2 has the spec in-file; do not implement the logic.

### Phase 3: Red contract tests against dev pgvector

- [x] **Task 5: DB-backed test fixtures** (depends on Task 4)
  Files: `tests/knowledge/__init__.py` (new), `tests/knowledge/conftest.py` (new)
  Provide async fixtures the three contract tests share:
  - A `dsn` helper building a Postgres DSN from `POSTGRES_*` env vars, defaulting to the dev database documented in `CLAUDE.md` (`localhost:5432`, db `herald_database`, user `herald_username`, password `herald_password`). (This task does NOT add `postgres_*` to `Settings` — that is 3.3.2; the tests read env directly.)
  - `pg_pool` — an async fixture that calls `create_pool(dsn)` (Task 2), applies `src/knowledge/schema.sql` (read the file, `await conn.execute(...)`), `TRUNCATE chunks` before yielding for isolation, yields the pool, and closes it on teardown.
  - `store` — returns `PgVectorStore(pg_pool)`.
  - A small helper to build `Chunk` objects with fixed 768-dim embeddings (e.g. a unit vector along a chosen axis) so cosine distances are deterministic and hand-computable.
  These fixtures connect to the dev pgvector database the project's first-time setup provisions; the tests are red because the stub raises, not because of the fixtures.

- [x] **Task 6: Three red contract tests** (depends on Task 5)
  Files: `tests/knowledge/test_knowledge_store_contract.py` (new)
  Write one async test per pinned invariant. Each is red now because `PgVectorStore`'s methods raise `NotImplementedError` (never an import/fixture error), and 3.3.2 turns them green unchanged:
  - **Cosine nearest-first order (adversarial).** `upsert` several chunks whose embeddings include one deliberately planted as the *farthest* by cosine from the query vector and one clearly nearest; `query(query_vec, k=all, repo=...)` and assert the returned order is nearest-first — the planted farthest vector MUST NOT be `result[0]`, and the nearest MUST be `result[0]`. Assert the explicit order (index positions), not merely membership, so a reversed `ORDER BY` fails this test.
  - **Atomic per-`(repo,path)` replace.** `upsert(repo, path, [5 chunks])`, then `upsert(repo, path, [2 chunks])`; assert the store now holds exactly 2 chunks for that `(repo, path)` with `chunk_index` `0,1` and no leftover indices `2..4` (verify by `query` results and/or a direct `SELECT chunk_index FROM chunks WHERE repo=$1 AND path=$2` via `pg_pool` — the PK already forbids duplicates, so the assertion targets the *replace*, not append).
  - **Path-scoped delete.** `upsert` chunks under two paths of the same repo (and optionally a second repo); `delete(repo, path_a)`; assert `path_a`'s chunks are gone while `path_b`'s (and any other repo's) chunks remain untouched.
