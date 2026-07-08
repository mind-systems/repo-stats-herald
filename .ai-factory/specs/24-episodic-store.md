# 4.1.2 — PgEpisodicStore (impl)

**Phase:** 4 — Episodic memory (the evolution log). Depends on 4.1.1 (the schema, the `EpisodicEntry` model, the `EpisodicStore` ABC, and its red tests). Second half of the store milestone — turns 4.1.1's tests green.

## Current state

4.1.1 lays the `episodic_entries` schema and the `EpisodicStore` ABC, and pins its contract (cosine ranking, `changed_at`-specific windowing, structural append-only) with red tests. The stub implementation raises for every call — no Postgres logic exists yet.

## Change

Implement `PgEpisodicStore` on 3.3's existing asyncpg pool — no second database.

- `src/episodic/store.py` — `PgEpisodicStore(EpisodicStore)`: reuses the `asyncpg` pool from `src/core/db.py` (3.3); `append(entry)` is a plain `INSERT` into `episodic_entries`, nothing else; `query(embedding, k, repo=None, since=None, until=None)` ranks by cosine distance, optionally scoped to `repo`, optionally windowed on `changed_at` when `since`/`until` are given.

## Files & types

- edit `src/episodic/store.py` (stub → `PgEpisodicStore` implementation)

## Guards

- **Append-only** — reuses 4.1.1's ABC, which has no `update`/`delete` method at all; this implementation adds none either.
- Reuses the existing Postgres pool (3.3) — no second database.
- Embedding dimension must equal the store column dimension — matches 3.2's embedder, a mismatch raises.
- **Concurrent appends are safe by construction** — `append` is a plain `INSERT` with no shared mutable state to race on; N concurrent callers each insert their own row independently.
- Turns 4.1.1's tests green — introduces no new contract beyond what 4.1.1 already pinned.

## Verification

- 4.1.1's red test suite passes green against this implementation.
- `append(entry)` twice for the same repo, then `query(embedding, k=5, repo="o/r")` → both entries eligible, ranked by similarity.
- No code path can remove or overwrite a stored entry.
- `query(embedding, k=5, since=<t1>, until=<t2>)` returns only entries whose `changed_at` falls in that window, regardless of when they were recorded.
