# Code Review: 6.1.2 — PgProjectGraph (impl)

**Scope reviewed:** `src/graph/store.py`, `src/core/config.py`, `src/main.py`, `.env.example`
**Plan:** `.ai-factory/plans/33-6-1-2-pgprojectgraph-impl.md`
**Tests:** `tests/graph/test_project_graph_contract.py` — all 4 cases pass green.

## Verdict

The implementation is correct and faithful to the plan and to spec `09-project-graph-registry.md`. The four pinned 6.1.1 cases (config-survives-collision, seed-only removal, directed neighbors, idempotent config reload) are satisfied, the config-parsing shape stays graph-agnostic (no `core/ → graph/` reverse import), and startup wiring loads config edges before push processing. No correctness, security, or runtime-breakage findings.

## What I verified

- **Conflict strategy is right.** `add_edge` branches on `edge.source`: `config` → `ON CONFLICT (from_repo, to_repo, kind) DO UPDATE SET source = EXCLUDED.source`; anything else (seed) → `DO NOTHING`. A seed write colliding with a stored `config` row is a no-op (source never downgraded); a `config` write reasserts `source='config'` even over a pre-existing seed row — the invariant holds by conflict strategy, not load-order timing, exactly as spec 09's guard requires. Idempotent config reload keeps one row.
- **No SQL injection.** The interpolated `conflict_clause` is a fixed literal selected by a branch, never derived from input. All values bind as `$1..$4` parameters.
- **`kind` round-trips cleanly.** Written as `edge.kind.value` (a plain string into the `text` column), hydrated back via `EdgeKind(row["kind"])`. `EdgeKind` is a `StrEnum`, so member value == member string; verified `edges_from` reconstructs the typed `Edge` with its stored `source`.
- **`neighbors` is directed** (`WHERE from_repo = $1`, `ORDER BY to_repo` for deterministic output) and `remove_seed_edges` deletes only `source='seed'`, sparing `config` rows.
- **Schema wiring.** `GRAPH_SCHEMA_PATH` is applied in the same startup `conn.execute(...)` block as the sibling schemas; `project_edges` is `CREATE TABLE IF NOT EXISTS`, so idempotent — the table exists before the first edge write.
- **Startup load** runs unconditionally (outside the GitHub-App/mirror gate), so operator edges load even when canonical-ref sync is disabled, and before `yield` (before any push processing). `EdgeKind(kind)` receives the already-upper-cased token from the validator; an unknown kind fails fast at startup — acceptable.
- **Config parsing** normalizes `kind` to upper-case and preserves case-sensitive `from_repo`/`to_repo`. Confirmed at runtime: `PROJECT_EDGES="a/x > a/y : contract , m>n:auth"` → `(('a/x','a/y','CONTRACT'), ('m','n','AUTH'))` — whitespace tolerant, `/` in repo names safe against the `>`/`:` delimiters, lowercase kind normalized. Malformed tokens (missing `>` or `:`) raise a clear `ValueError`. `.env.example` documents the grammar mirroring the sibling entries.
- **Import sanity.** `import src.main` succeeds; no circular-import or missing-symbol issues introduced by the new `src.graph` imports.

## Deferred observations (not defects in this task's scope)

- **Dropped config edges are not pruned at startup.** The startup loop only upserts the currently-declared `PROJECT_EDGES`; it never removes a `config` row for an edge an operator has since deleted from the env. `remove_seed_edges` handles only `source='seed'`, so a removed config edge lingers in `project_edges` across restarts. Spec 09's verification requires only idempotent reload of *present* edges, not removal of absent ones, so this is in-spec for 6.1.2 — flagging for whoever owns config-edge lifecycle later (a "replace the config-sourced set at startup" sweep would close it).
- **`neighbors` can return a duplicate `to_repo`** when two edges of different `kind` link the same pair (no `DISTINCT`). This matches the pinned 6.1.1 contract ("the `to_repo` of every edge") and current tests; the eventual neighbors-consumer (Phase 7 cross-project reach) should decide whether it wants distinct project neighbors and de-dupe there. Already noted in plan-review-1.

REVIEW_PASS
