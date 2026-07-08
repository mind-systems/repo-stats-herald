# 4.1.1 — Episodic store contract + schema (red tests)

**Phase:** 4 — Episodic memory (the evolution log). Depends on Phase 3 (Postgres already provisioned via 3.3's pool/DSN) and 3.2 (the embedder). First half of the store milestone — the schema + seam, pinned with red tests, ahead of the pgvector implementation (4.1.2).

## Current state

Herald has no persistence for *how* a project changed over time. `KnowledgeStore` (3.3) is current-state-only — `upsert` replaces a `(repo, path)`'s chunks, so a superseded or removed artifact leaves no trace. A `LinkedChange` (4.2) is resolved but nothing retains it once consumed. Worse, nothing pins the store's most dangerous failure mode: a `since`/`until` query wired to `recorded_at` (server-assigned on insert) instead of `changed_at` (the commit's own timestamp) would silently collapse an entire backfilled history into the ingest moment — plausible-looking, no exception. This is the episodic analog of 3.3.1's cosine-order hazard.

## Change

Lay the schema and the `EpisodicStore` ABC, then pin its contract with red tests before writing the pgvector implementation.

- `src/episodic/models.py` — `EpisodicEntry` (immutable): `repo: str`, `org_id: int`, `completed_tasks: tuple[str, ...]`, `commit_shas: tuple[str, ...]`, `content: str` (the text that gets embedded — completed task titles + commit messages), `embedding: list[float]`, `changed_at: datetime` (the **commit** timestamp — the historical truth, the temporal key for "6 months ago" queries), `recorded_at: datetime` (server-assigned ingest bookkeeping, distinct from `changed_at`).
- `src/episodic/schema.sql` — table `episodic_entries` (`id bigserial PRIMARY KEY`, `repo text`, `org_id bigint`, `completed_tasks text[]`, `commit_shas text[]`, `content text`, `embedding vector(<dim>)`, `changed_at timestamptz`, `recorded_at timestamptz DEFAULT now()`), an ANN index on `embedding` (cosine ops) and a btree index on `(repo, changed_at)`.
- `src/episodic/store.py` — `EpisodicStore` (ABC): `append(entry: EpisodicEntry) -> None`, `query(embedding: list[float], k: int, repo: str | None = None, since: datetime | None = None, until: datetime | None = None) -> list[EpisodicEntry]`. Names no Postgres concept. **No `update`/`delete` method exists at all** — append-only is structural, not a caller convention. A STUB implementation raises for now.
- Write red tests against the stub/schema pinning:
  - `query` ranks results by cosine similarity (nearest-first);
  - `since`/`until` filter on **`changed_at` specifically** — plant an entry whose `changed_at` falls outside the window but whose `recorded_at` falls inside it (and vice versa); it must not leak in on `recorded_at`, and must not leak out when only `changed_at` is in-window;
  - the `EpisodicStore` ABC exposes no `update`/`delete` — append-only is enforced by the interface's shape, not a runtime check.

## Files & types

- new `src/episodic/__init__.py`, `src/episodic/models.py` (`EpisodicEntry`), `src/episodic/store.py` (`EpisodicStore` ABC + stub), `src/episodic/schema.sql`
- new test file(s) covering the cases above, run against a dev pgvector (red)

## Guards

- Tests-first: the stub raises rather than persisting — 4.1.2 turns these tests green, never the reverse.
- The `changed_at`/`recorded_at` test is explicit and adversarial (a planted entry with a misleading value on the *other* column) — a merely-passing "query returns something" test would not catch the wrong column being filtered.
- `EpisodicStore` names no Postgres concept — the backend swaps without touching callers (mirrors `KnowledgeStore`'s discipline).
- Embedding dimension must equal the schema's column dimension — matches 3.2's embedder, a mismatch raises.

## Verification

- The test suite added here is red against the stub (fails only because there's no append/query logic yet).
- The schema applies cleanly alongside 3.3's (same Postgres, same `vector` extension).
- Each of the three pinned cases (cosine rank, `changed_at`-specific windowing, structural append-only) has a corresponding red test.
