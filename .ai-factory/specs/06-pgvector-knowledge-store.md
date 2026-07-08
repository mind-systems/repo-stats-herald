# 3.3.2 — PgVectorStore (impl)

**Phase:** 3 — Repo mirror & semantic memory. Depends on 3.3.1 (the schema, the `KnowledgeStore` ABC, and its red tests). Second half of the store milestone — turns 3.3.1's tests green.

## Current state

3.3.1 lays the `chunks` schema and the `KnowledgeStore` ABC, and pins its contract (cosine ordering, atomic replace, scoped delete) with red tests. The stub implementation raises for every call — no pgvector query logic exists yet.

## Change

Implement `PgVectorStore` over 3.3.1's pool and schema, and extend `Settings` with the Postgres connection.

- Extend `src/core/config.py` `Settings` with `postgres_host/port/user/password/db`, and a derived DSN.
- `src/knowledge/store.py` — `PgVectorStore(KnowledgeStore)`: `upsert` = delete-then-insert per `(repo, path)` in one transaction (idempotent — re-upserting replaces, never appends; crash-safe — a failed txn leaves the prior chunks intact); `query` orders by cosine distance (cosine ops per the ANN index), optionally scoped to a repo.

## Files & types

- edit `src/core/config.py` (`postgres_*`, DSN)
- edit `src/knowledge/store.py` (stub → `PgVectorStore` implementation)

## Guards

- Connection params from env via `Settings`; assumes the `vector` extension exists (dev-setup / prod image).
- Upsert is per-`(repo, path)` and idempotent (replace, not append); one txn, so a crash leaves prior chunks intact.
- Embedding dimension must equal the store column dimension — a mismatch raises, never silently truncates.
- **Out-of-order same-ref writes are benign and self-healing** — if two upserts for the same `(repo, path)` at the same ref land out of order (e.g. a retried request), the last write wins and the content is identical either way; the next push on the canonical ref re-syncs regardless, so no version/ordering guard is needed here.
- Turns 3.3.1's tests green — introduces no new contract beyond what 3.3.1 already pinned.

## Verification

- 3.3.1's red test suite passes green against this implementation.
- `upsert("o/r", "CLAUDE.md", [chunk...])` then `query(vec, k=3, repo="o/r")` returns nearest chunks by cosine.
- `delete("o/r", "CLAUDE.md")` removes only that path's chunks.
- Re-`upsert` of the same `(repo, path)` replaces (no duplicate `chunk_index`).
