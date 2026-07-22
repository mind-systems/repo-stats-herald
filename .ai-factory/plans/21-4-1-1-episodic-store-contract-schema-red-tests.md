# Plan: 4.1.1 — Episodic store contract + schema (red tests)

## Context
Lay the append-only episodic memory seam — the `EpisodicEntry` model, `episodic_entries` schema, and `EpisodicStore` ABC (with a raising stub) — and pin its contract with red tests before the pgvector implementation lands in 4.1.2. The dangerous failure mode being pinned: a `since`/`until` window wired to `recorded_at` (ingest time) instead of `changed_at` (commit time) would silently collapse backfilled history into the ingest moment.

This is the direct analog of the shipped knowledge store (3.3.1/3.3.2). Mirror its proven shapes: `src/knowledge/store.py` (ABC + concrete over an asyncpg pool), `src/knowledge/schema.sql` (vector column + hnsw cosine index), `tests/knowledge/conftest.py` + `tests/knowledge/test_knowledge_store_contract.py` (pool fixture applying schema + `TRUNCATE`, unit-vector cosine fixtures). The pgvector `vector` type marshals as `list[float]` on both ends via the codec registered in `src/core/db.py` `create_pool` — no wire-format handling in feature code.

## Settings
- Testing: yes
- Logging: none
- Docs: no

## Tasks

### Phase 1: Contract + schema

- [x] **Task 1: `EpisodicEntry` value object**
  Files: `src/episodic/__init__.py` (new, empty), `src/episodic/models.py` (new)
  Add a frozen dataclass `EpisodicEntry` (`from dataclasses import dataclass`, `@dataclass(frozen=True)`; `from datetime import datetime`), mirroring `Chunk`'s immutable-value style in `src/knowledge/store.py`. Fields exactly per spec:
  - `repo: str`
  - `org_id: int`
  - `completed_tasks: tuple[str, ...]`
  - `commit_shas: tuple[str, ...]`
  - `content: str` — the text that gets embedded (completed task titles + commit messages; assembled by the 4.3 writer, not here)
  - `embedding: list[float]`
  - `changed_at: datetime` — the **commit** timestamp; the historical/temporal key for "6 months ago" queries
  - `recorded_at: datetime` — server-assigned ingest bookkeeping, distinct from `changed_at`
  Give `recorded_at` a default so callers appending fresh entries need not fabricate an ingest time (e.g. `recorded_at: datetime | None = None`; the store assigns the real value from the DB `now()` default). Keep the model pure — no Postgres, no I/O.

- [x] **Task 2: `episodic_entries` schema**
  Files: `src/episodic/schema.sql` (new)
  Follow `src/knowledge/schema.sql` exactly in structure. Lead with `CREATE EXTENSION IF NOT EXISTS vector;` and use `CREATE TABLE IF NOT EXISTS` / `CREATE INDEX IF NOT EXISTS` so it applies idempotently alongside the `chunks` schema on the same database. Table `episodic_entries`:
  - `id bigserial PRIMARY KEY`
  - `repo text NOT NULL`
  - `org_id bigint NOT NULL`
  - `completed_tasks text[] NOT NULL`
  - `commit_shas text[] NOT NULL`
  - `content text NOT NULL`
  - `embedding vector(768) NOT NULL` — dimension 768, matching 3.2's embedder and the `chunks` column; a mismatch must raise, never truncate (enforced by 4.1.2, pinned by the column width here)
  - `changed_at timestamptz NOT NULL`
  - `recorded_at timestamptz NOT NULL DEFAULT now()`
  ANN index for cosine retrieval: `CREATE INDEX IF NOT EXISTS episodic_entries_embedding_cos_idx ON episodic_entries USING hnsw (embedding vector_cosine_ops);` (same operator class as `chunks_embedding_cos_idx`). Windowing btree: `CREATE INDEX IF NOT EXISTS episodic_entries_repo_changed_at_idx ON episodic_entries (repo, changed_at);`.

- [x] **Task 3: `EpisodicStore` ABC + raising stub** (depends on Task 1)
  Files: `src/episodic/store.py` (new)
  Mirror the `KnowledgeStore` ABC / `PgVectorStore` split in `src/knowledge/store.py`, but append-only. Import `EpisodicEntry` from `src/episodic/models.py` (keep the model in `models.py`, unlike knowledge which inlined `Chunk` — follow the ARCHITECTURE feature template: `models.py` owns value objects).
  - `EpisodicStore(ABC)` with **only** two `@abstractmethod`s — the interface's shape is the append-only guarantee, so **no `update`/`delete`/`upsert` method exists at all**:
    - `async def append(self, entry: EpisodicEntry) -> None` — docstring: appends one entry; the log is append-only, entries are never mutated or removed.
    - `async def query(self, embedding: list[float], k: int, repo: str | None = None, since: datetime | None = None, until: datetime | None = None) -> list[EpisodicEntry]` — docstring: return up to `k` entries ordered nearest-first by cosine distance to `embedding`, optionally scoped to `repo`; `since`/`until` bound the window on **`changed_at`** (the commit timestamp — the historical key), never on `recorded_at`.
    The ABC names no Postgres/pgvector concept (mirrors `KnowledgeStore`'s discipline), so 4.1.2's backend swaps without touching callers.
  - `PgEpisodicStore(EpisodicStore)` — the stub 4.1.2 will flesh out. `__init__(self, pool: asyncpg.Pool)` stores the pool (same shape as `PgVectorStore.__init__`); both `append` and `query` bodies `raise NotImplementedError` for now. This is the class the tests instantiate, so 4.1.2 greens them by filling these bodies — never by weakening the tests.

### Phase 2: Red tests

- [x] **Task 4: Test fixtures** (depends on Task 2, Task 3)
  Files: `tests/episodic/__init__.py` (new, empty), `tests/episodic/conftest.py` (new)
  Copy the structure of `tests/knowledge/conftest.py`:
  - `SCHEMA_PATH` → `src/episodic/schema.sql`; `EMBEDDING_DIM = 768`.
  - `_dsn()` reading `POSTGRES_*` env with the same defaults (`localhost`/`5432`/`herald_username`/`herald_password`/`herald_database`).
  - `pg_pool` async fixture: `create_pool(_dsn())` (from `src/core/db.py`), apply the schema, `TRUNCATE episodic_entries`, yield, close.
  - `store` fixture returning `PgEpisodicStore(pg_pool)`.
  - `make_entry` factory (analog of `make_chunk`): builds an `EpisodicEntry` from a `content` + `axis`/`value` unit-vector embedding (`[0.0] * EMBEDDING_DIM` with one axis set), and accepts a `changed_at` argument so the windowing test can plant historical timestamps. Give it sensible defaults for `repo`, `org_id`, `completed_tasks`, `commit_shas`.
  - **Timestamps are timezone-aware, always.** This is the episodic store's first use of `timestamptz`; the knowledge tests carry no precedent to inherit. Every `changed_at` the factory builds and every `since`/`until` boundary the tests pass must be **tz-aware** (`from datetime import datetime, timezone`; anchor on `datetime.now(timezone.utc)` and offset with `timedelta`). Rationale (verified against asyncpg's `timestamptz` codec): a **naive** datetime does not raise on encode — asyncpg treats it as machine-local and shifts it by the host's UTC offset, so naive boundaries move per-timezone and make boundary-adjacent windows flaky across environments; and the decoder returns tz-aware UTC datetimes, so any Python-side comparison against a naive reference raises `TypeError: can't compare offset-naive and offset-aware`. Default `changed_at` to a fixed aware value (e.g. `datetime(2024, 1, 1, tzinfo=timezone.utc)`) so callers that don't care never trip on tz-awareness.

- [x] **Task 5: Contract tests (red against the stub)** (depends on Task 4)
  Files: `tests/episodic/test_episodic_store_contract.py` (new)
  Three tests, mirroring `tests/knowledge/test_knowledge_store_contract.py`. The two behavioral tests plant via `store.append(...)` then assert on `store.query(...)`; both calls hit the raising stub, so the suite is **red** — 4.1.2 turns it green.
  - `test_query_orders_results_nearest_first_by_cosine` — append three entries at unit vectors: same-direction (distance 0), orthogonal (distance 1), opposite (distance 2); `query(unit_vector(axis=0), k=3)` must return them nearest-first. Assert the exact order (as the knowledge test does), so a reversed/wrong `ORDER BY` cannot pass.
  - `test_since_until_filter_on_changed_at_not_recorded_at` — the adversarial core. Because `append` server-assigns `recorded_at = now()`, both misleading-value directions are constructed against a plausibly-wrong `recorded_at`-based filter. Build every `changed_at`, `since`, and `until` as **tz-aware UTC** (see Task 4), and keep the misleading-`recorded_at`-to-window distance comfortably larger than any host UTC offset (use day/week gaps, not minutes) so no boundary sits close enough to the edge for a stray offset to flip the assertion:
    - **Must-not-leak-in:** an entry with an OLD `changed_at` (well in the past) but a fresh `recorded_at` (≈ now). Query a window whose `since` is recent (includes `recorded_at` = now but excludes the old `changed_at`). The entry must be **absent** — proving the filter is on `changed_at`, not `recorded_at`.
    - **Must-not-leak-out:** an entry with a `changed_at` inside a historical window `[t0, t1]` entirely in the past (so `recorded_at` ≈ now falls **outside** it). Query `since=t0, until=t1`. The entry must be **present** — proving an in-window `changed_at` is not dropped merely because `recorded_at` sits outside the window.
    Include at least one clearly in-window and one clearly out-of-window entry so each assertion is unambiguous. A plain "query returns something" test would not catch the wrong column — these planted misdirections are the point.
  - `test_episodic_store_is_structurally_append_only` — assert the interface shape carries the append-only guarantee: `not hasattr(EpisodicStore, "update")`, `not hasattr(EpisodicStore, "delete")`, `not hasattr(EpisodicStore, "upsert")` (and the same for `PgEpisodicStore`). Note for the implementer: this is a **structural guard** (per the spec's "enforced by the interface's shape, not a runtime check") — it passes as soon as the ABC is written with no mutation methods, so it does not itself go red-then-green; the two behavioral tests above carry the red. Keeping it in the suite pins that no future task quietly adds a mutation method.
