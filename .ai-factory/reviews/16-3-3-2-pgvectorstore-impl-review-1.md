# Code Review: 3.3.2 — PgVectorStore (impl)

## Summary

**Files reviewed (in full):** `src/core/config.py`, `src/knowledge/store.py`, against `src/core/db.py`, `src/knowledge/schema.sql`, `tests/knowledge/conftest.py`, `tests/knowledge/test_knowledge_store_contract.py`, `tests/conftest.py`, `Makefile`, `pyproject.toml`, and the governing spec `.ai-factory/specs/06-pgvector-knowledge-store.md`.
**Risk level:** 🟢 Low

The change implements `PgVectorStore.upsert/delete/query` over the injected asyncpg pool and extends `Settings` with `postgres_*` fields plus a derived `postgres_dsn` property. It greens 3.3.1's red suite and faithfully implements the plan and spec.

## Verification performed

- Ran `pytest tests/knowledge/` against a live local pgvector database: **3 passed** (cosine-order, atomic replace, scoped delete).
- Ran the full suite (`pytest`): **11 passed** — the shared `Settings` change did not regress the webhook/ingestion suites.

## Correctness checks (all pass)

- **Atomic replace / crash-safety.** `upsert` runs `DELETE` + `executemany(INSERT)` inside `async with self._pool.acquire() as conn, conn.transaction()`. A failing INSERT (including a dimension mismatch) rolls back the DELETE in the same transaction, so prior chunks survive — the spec's "failed txn leaves prior chunks intact" guard holds.
- **Idempotent, index-derived `chunk_index`.** `enumerate(items)` assigns `chunk_index` from method args, ignoring the incoming chunks' own `None` fields; a 5→2 re-upsert leaves exactly `[0, 1]` (no stale higher indices) — matches `test_upsert_atomically_replaces_prior_chunks_for_the_path`.
- **Empty `items`.** `rows` is empty → DELETE runs, INSERT is skipped → the path is cleared. Consistent with "replace all chunks with items."
- **Cosine ordering.** `ORDER BY embedding <=> $N` uses the cosine-distance operator matching the `vector_cosine_ops` HNSW index in `schema.sql`; `<->`/`<#>` correctly avoided. Confirmed by the distance-0/1/2 fixture asserting nearest-first order.
- **Query embedding codec.** asyncpg infers `$N` as `vector` from the `<=>` signature, so the `vector` text codec registered in `src/core/db.py` encodes the raw `list[float]`; the decode codec hydrates the returned `embedding`, populating `Chunk`'s required `embedding` field.
- **Repo scope + positional params.** `repo is None` → `(embedding, k)` on `$1/$2`; scoped → `(repo, embedding, k)` on `$1/$2/$3`. SQL and params align in both branches.
- **Scoped delete.** Single `DELETE ... WHERE repo = $1 AND path = $2`, reused via `_DELETE_SQL` in both `delete` and `upsert` — no SQL duplication; leaves other paths/repos untouched.
- **Dimension guard.** No client-side slicing or padding; `vector(768)` rejects a wrong-dimension vector on insert and comparison, so a mismatch raises rather than truncating.
- **Injection.** All values are parameterized; no string interpolation of user data into SQL.
- **`Settings` invariant.** All five `postgres_*` fields are defaulted to the conftest's own values, keeping `Settings()` constructible from the webhook secret alone — the full suite passing under a bare `pytest` (no `.env.dev`) confirms the webhook/ingestion suites are unaffected. `postgres_dsn` reproduces the exact shape `conftest._dsn()` builds.

## Non-blocking notes (no action required for this task)

- `postgres_dsn` interpolates user/password into the URL without percent-encoding. Out of scope per the plan and mirrors the conftest's identical unescaped `_dsn()`; a password containing URL-reserved characters would corrupt both. Flagged for whoever hardens production Postgres config — not a defect of this change.
- `query`'s local `params` is assigned a 2-tuple in one branch and a 3-tuple in the other. No type-checker runs in the project flow (`make test` is `pytest` only), so this is a non-issue at runtime; a strict mypy pass would flag the union.

No correctness, security, or runtime defects found.

REVIEW_PASS
