# Plan: 4.1.2 — PgEpisodicStore (impl)

## Context
Turn 4.1.1's red episodic-store tests green by implementing `PgEpisodicStore.append` (plain `INSERT`) and `PgEpisodicStore.query` (cosine rank with optional `changed_at` window, repo-scoped) over 3.3's existing asyncpg pool — no second database.

## Settings
- Testing: no
- Logging: minimal
- Docs: no

## Notes for the implementer
- Ground truth is the existing code, not this plan. The only production file to edit is `src/episodic/store.py`; the ABC, model, schema, and the red suite already exist from 4.1.1 and must not change.
- Follow `src/knowledge/store.py` (`PgVectorStore`) exactly as the reference pattern — same pool usage, same `<=>` cosine operator, same `conn.fetch`/`conn.execute` shape. The `vector` type marshals to/from `list[float]` automatically via the codec registered in `src/core/db.py`; pass the embedding list straight through as a query param, never hand-encode it.
- Table `episodic_entries` (see `src/episodic/schema.sql`): columns `id`, `repo`, `org_id`, `completed_tasks text[]`, `commit_shas text[]`, `content`, `embedding vector(768)`, `changed_at`, `recorded_at timestamptz NOT NULL DEFAULT now()`.
- The red suite lives in `tests/episodic/test_episodic_store_contract.py`; fixtures (`store`, `make_entry`, pool truncation) are in `tests/episodic/conftest.py`. Running it needs a dev pgvector (`herald_database`).

## Tasks

### Phase 1: Implement PgEpisodicStore

- [x] **Task 1: Implement `append` as a plain INSERT**
  Files: `src/episodic/store.py`
  Replace the `NotImplementedError` body of `append(self, entry)` with a single `INSERT` into `episodic_entries`. Acquire from the pool (`async with self._pool.acquire() as conn`) and `await conn.execute(...)`.
  - Insert the columns `repo, org_id, completed_tasks, commit_shas, content, embedding, changed_at` from `entry`; pass `list(entry.completed_tasks)` and `list(entry.commit_shas)` (the model stores tuples; asyncpg wants a sequence for `text[]`), and pass `entry.embedding` directly (codec handles `vector`).
  - **Do NOT set `recorded_at`** — let the column's `DEFAULT now()` fire, so a backfilled entry (old `changed_at`) still gets a fresh server-assigned `recorded_at`. This is exactly what the `since/until` test relies on.
  - No transaction wrapper is needed (single statement); no shared mutable state — concurrent appends are safe by construction, each inserting its own row.
  - Add no `update`/`delete`/`upsert` method (the structural append-only test asserts their absence).

- [x] **Task 2: Implement `query` as cosine rank with optional changed_at window** (depends on Task 1)
  Files: `src/episodic/store.py`
  Replace the `NotImplementedError` body of `query(self, embedding, k, repo=None, since=None, until=None)`.
  - Build the SQL dynamically over positional params so absent filters add no predicate: collect `WHERE` clauses for `repo = $n` (when `repo is not None`), `changed_at >= $n` (when `since is not None`), and `changed_at <= $n` (when `until is not None`), appending each value to a params list in lockstep so the `$n` numbering stays correct. Bounds are inclusive (`>=` / `<=`).
  - **Window on `changed_at`, never `recorded_at`** — this is the pinned hazard from 4.1.1 (a `recorded_at` filter silently collapses backfilled history into the ingest moment).
  - `SELECT repo, org_id, completed_tasks, commit_shas, content, embedding, changed_at, recorded_at`, then `ORDER BY embedding <=> $n` (cosine distance, nearest-first) and `LIMIT $n` with `k`.
  - Fetch with `conn.fetch(sql, *params)` and map each row to an `EpisodicEntry`, converting `completed_tasks`/`commit_shas` back to tuples and hydrating `changed_at`/`recorded_at`; `embedding` returns as `list[float]` via the codec.
  - Embedding-dimension mismatch needs no explicit check: the `vector(768)` column and the `<=>` operator make Postgres raise on a wrong-length vector — the guard ("dim matches 3.2's embedder or raises") holds by construction, matching `PgVectorStore`.

## Verification
- `tests/episodic/test_episodic_store_contract.py` passes green (cosine ordering; `since`/`until` filtering on `changed_at` with the misleading `recorded_at` planted entries; structural append-only).
- No code path can remove or overwrite a stored entry.
