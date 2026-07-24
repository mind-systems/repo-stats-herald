# 3.3.1 — KnowledgeStore contract + schema (red tests)

**Phase:** 3 — Repo mirror & semantic memory. Herald's own Postgres (`herald_database`, `vector` extension) is already provisioned. First half of the store milestone — the seam + schema, pinned with red tests, ahead of the pgvector implementation (3.3.2).

## Current state

Herald has no database access at all. `Settings` reads Ollama/SSH/GitHub env but not `POSTGRES_*` (present in `.env.dev`/`.env.example`). The knowledge store described in `docs/behavior/understanding.md` (per-project retrieval store on pgvector) has no schema, no code, and no test pinning its most dangerous failure mode: a wrong cosine `ORDER BY` direction returns the *farthest* chunks labeled as "nearest" — plausible-looking, no exception.

## Change

Lay the persistence pool, the `chunks` schema, and the `KnowledgeStore` ABC, then pin its contract with red tests before writing the pgvector query logic.

- `src/core/db.py` — an `asyncpg` connection pool created at the composition root from the DSN.
- Migration / schema (`src/knowledge/schema.sql`): table `chunks` — `repo text`, `path text`, `chunk_index int`, `content text`, `embedding vector(<dim>)`, `PRIMARY KEY (repo, path, chunk_index)`; an ANN index (`hnsw` or `ivfflat`) on `embedding` with cosine ops. `<dim>` matches the `embed_model` dimension (3.2).
- `src/knowledge/store.py` — `KnowledgeStore` (ABC): `upsert(repo, path, items: list[Chunk])`, `delete(repo, path)`, `query(embedding: list[float], k: int, repo: str | None = None) -> list[Chunk]`. Names no pgvector concept. A STUB implementation raises for now.
- Write red tests against the stub/schema pinning:
  - `query` returns chunks in **true nearest-first** order by cosine distance (a deliberately-planted farthest-vector fixture must NOT rank first — the ORDER direction is explicitly asserted, not just "some order");
  - `upsert` replaces a `(repo, path)`'s prior chunks atomically — no duplicate `chunk_index` after a re-upsert with a different chunk count;
  - `delete` clears only the targeted path's chunks, leaving other paths untouched.

## Files & types

- new `src/core/db.py` (pool), `src/knowledge/schema.sql`, `src/knowledge/store.py` (`Chunk`, `KnowledgeStore` ABC + stub)
- new test file(s) covering the three contract cases above, run against a dev pgvector (red)

## Guards

- Tests-first: the stub raises rather than querying — 3.3.2 turns these tests green, never the reverse.
- The cosine-ORDER test is explicit and adversarial (a planted farthest vector) — a merely-passing "returns some rows" test would not catch a reversed `ORDER BY`.
- `KnowledgeStore` seam names no pgvector concept — the backend swaps (a time-series or other store later) without touching callers.
- Embedding dimension must equal the schema's column dimension — a mismatch raises, never silently truncates.

## Verification

- The test suite added here is red against the stub (fails only because there's no query/upsert/delete logic yet).
- The schema applies cleanly against a dev pgvector database.
- Each of the three contract cases (cosine order, atomic replace, scoped delete) has a corresponding red test.
