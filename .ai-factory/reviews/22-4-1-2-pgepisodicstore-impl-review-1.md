# Code Review: 4.1.2 — PgEpisodicStore (impl)

**Plan:** `.ai-factory/plans/22-4-1-2-pgepisodicstore-impl.md`
**Changed production files:** `src/episodic/store.py` (only)
**Reviewed against:** `src/episodic/models.py`, `src/episodic/schema.sql`, `src/core/db.py`, `src/knowledge/store.py`, `tests/episodic/test_episodic_store_contract.py`, `tests/episodic/conftest.py`, spec `.ai-factory/specs/24-episodic-store.md`

## Scope
Only `src/episodic/store.py` changed (plus planning artifacts). The ABC, model, schema, and red suite are untouched, as the plan required.

## Correctness verification

- **`append` INSERT** — inserts `repo, org_id, completed_tasks, commit_shas, content, embedding, changed_at`; every column is `NOT NULL` in `schema.sql` and every value is present on `EpisodicEntry`. `recorded_at` is correctly omitted so the column `DEFAULT now()` fires — the exact precondition `test_since_until_filter_on_changed_at_not_recorded_at` depends on (old `changed_at`, fresh `recorded_at`). `list(entry.completed_tasks)` / `list(entry.commit_shas)` correctly adapt the frozen model's tuples to sequences for `text[]`; `entry.embedding` passes straight to the `vector` codec registered in `core/db.py`. Single statement, own pooled connection — concurrent appends are safe by construction.

- **`query` dynamic WHERE + params** — filter values are appended to `params` in lockstep with `f"... ${len(params)}"`, so positional numbering stays correct for every combination of `repo`/`since`/`until`/none. The `embedding` and `k` params are appended last and referenced by captured indices (`order_param`, `limit_param`). I checked the non-obvious risk that placing the embedding param *after* the filter params (unlike `PgVectorStore`'s fixed positions) could break type inference: it does not — Postgres infers the operand type of `$order_param` from its use in `embedding <=> $order_param`, independent of ordinal position, so no `::vector` cast is needed. All interpolated fragments are integers derived from `len(params)` — no SQL injection surface.

- **Cosine ordering** — `ORDER BY embedding <=> $n LIMIT $n` ascending on cosine distance yields nearest-first, matching `test_query_orders_results_nearest_first_by_cosine` (distance 0 / 1 / 2 for the three planted vectors).

- **`changed_at` windowing (the pinned hazard)** — `since`/`until` compare `changed_at`, never `recorded_at`, with inclusive `>=`/`<=`. Traced against the test: the recent-window query (`since` only) admits `in-recent-window`, excludes `misleading-old-changed-fresh-recorded` and `outside-both-windows`; the historical `[t0, t1]` query admits `misleading-historical-...` (changed_at = t0+5d) and excludes the controls. Correct.

- **Hydration** — every selected column maps back to `EpisodicEntry`, converting `text[]` → tuple for the frozen dataclass and returning `recorded_at`; `embedding` decodes to `list[float]` via the codec.

- **Structural append-only** — no `update`/`delete`/`upsert` added; `test_episodic_store_is_structurally_append_only` holds.

- **Dim mismatch** — no explicit check, correctly relying on the `vector(768)` column / `<=>` operator to raise on a wrong-length vector, matching `PgVectorStore` and the spec guard.

## Runtime / integration checks
- No migration needed — `schema.sql` already ships `episodic_entries` and its indexes, and the conftest applies it before each test.
- Pool usage (`self._pool.acquire()`, `conn.execute`/`conn.fetch`) mirrors `PgVectorStore` exactly; the pool's per-connection `vector` codec applies on both encode and decode.
- No cross-feature imports; DI via constructor preserved.

## Findings
None. The implementation is correct, matches the plan and spec, and greens 4.1.1's contract.

REVIEW_PASS
