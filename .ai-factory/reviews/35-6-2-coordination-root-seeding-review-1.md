# Code Review: 6.2 — Coordination-root seeding

**Plan:** `.ai-factory/plans/35-6-2-coordination-root-seeding.md`
**Spec:** `.ai-factory/specs/10-coordination-root-seeding.md`
**Format contract:** `docs/behavior/coordination-root-format.md`

## Scope reviewed (code only; planning docs excluded)

- `src/graph/coordination.py` (new — `CoordinationSeeder`)
- `src/graph/store.py` (`replace_seed_edges` added to ABC + `PgProjectGraph`)
- `src/knowledge/sync.py` (optional `seeder`, calls in `backfill` + canonical branch of `on_push`)
- `src/main.py` and `scripts/backfill.py` (both composition roots wired)
- `tests/graph/test_coordination_seeder.py` (new) + `tests/graph/test_project_graph_contract.py` (replace/concurrency tests)

## Verification performed

- **AST-parsed** all six changed files — no syntax errors.
- **No broken callers:** the only `KnowledgeSync(` constructions are `src/main.py:78` and `scripts/backfill.py:63`, both now passing the new 5th arg; `seeder` defaults to `None` so no other path breaks.
- **Fixtures:** the new `tests/graph/test_coordination_seeder.py` lives under `tests/graph/`, so `store`/`make_edge`/`pg_pool` from `tests/graph/conftest.py` resolve. `asyncio` and `Edge` are imported in the contract test that uses them.
- **Pool sizing:** `create_pool` uses asyncpg defaults (min/max 10) — the two-connection `asyncio.gather` concurrency test cannot exhaust the pool or deadlock.

## Correctness assessment

The implementation faithfully matches the spec and the format contract. Key points confirmed:

- **Atomic replace (`replace_seed_edges`)** — single acquired connection inside `async with ... conn.transaction()`, `pg_advisory_xact_lock(hashtext($1))` taken first (int4→bigint single-arg overload, unambiguous; xact lock releases at commit), `DELETE ... source='seed'` only, then per-edge `INSERT ... ON CONFLICT (from_repo,to_repo,kind) DO NOTHING`. A colliding `config` row survives (config wins); concurrent replaces for the same repo serialize on the advisory lock and cannot interleave a partial/duplicated set. The delete and inserts are inside the lock-held transaction, so no window for a mixed set. Config rows are never touched by the `source='seed'` delete predicate.
- **Bare identity on both endpoints** — `seed`'s `repo` (bare `push.repo`) is used as `from_repo`; the Member cell is used verbatim as `to_repo`. Never `org/repo`.
- **Section isolation** — `_coordination_section` collects only lines between the exact `## Coordination` heading and the next `## ` heading; a preceding `## Commands` table (before the section starts) and a trailing `## Other` section are excluded. `_parse_members` correctly skips the header row (`member`), the `-`/`:`/space separator row, and empty-Member rows, and maps kinds via the first `[\s:]+` token (`contract`→CONTRACT, `auth`→AUTH, else/empty→DEPENDENCY). The `worker` row with an empty Relationship maps to DEPENDENCY. Boundary-cell trimming handles the leading/trailing `|` empties without collapsing genuinely-empty Member rows.
- **Empty-replace on missing/non-root** — a missing `CLAUDE.md` (`text is None`) or a file without `## Coordination` yields `edges=[]`, so `replace_seed_edges(repo, [])` drops stale seeds. Verified by `test_seed_drops_all_seed_edges_when_section_removed` / `...when_file_missing`.
- **Canonical-ref gating** — the `on_push` seed call sits after the existing non-canonical early return, so a feature-branch push never seeds. `seed` re-resolves the canonical ref exactly as `KnowledgeSync` does.
- **No fetch in the seeder** — `seed` opens `mirror.tree` and reads `CLAUDE.md` but never calls `ensure`; both callers (`backfill`, `on_push`) call `mirror.ensure(...)` before reaching the seed call, so the bare clone / `default_branch` prerequisites hold. Guard satisfied.
- **Both composition roots wired** — the review-1 dead-path issue is resolved: `scripts/backfill.py` now applies `graph/schema.sql`, builds `PgProjectGraph`, and injects the seeder.
- **No new schema/migration** — `replace_seed_edges` reuses the existing `project_edges` table and PK.
- **No import cycle** — `coordination` → `store`/`models`/`mirror`; `sync` → `coordination`; no back-edge.

## Non-blocking note (not a defect against the current spec)

`is_coordination_root` / `_coordination_section` match `## Coordination` on any line, with no awareness of fenced code blocks. A `CLAUDE.md` that *documents* the coordination format inside a ```` ```markdown ```` fence (containing a literal `## Coordination` example table) would be recognized as a coordination root and its example rows seeded as edges. This exactly matches the format contract's recognition rule ("carries a `## Coordination` section") and the spec, which define recognition purely by heading presence and mention no fence handling, so it is not a defect here — flagged only for awareness should a future revision want fence-aware parsing. Realistic coordination-root `CLAUDE.md` files declare the section for real rather than as a fenced example, so no runtime break is expected.

REVIEW_PASS
