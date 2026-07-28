# Plan Review: 6.2 — Coordination-root seeding

**Plan:** `.ai-factory/plans/35-6-2-coordination-root-seeding.md`
**Spec:** `.ai-factory/specs/10-coordination-root-seeding.md` (contract line: ROADMAP.md 6.2)
**Format contract:** `docs/behavior/coordination-root-format.md`
**Risk Level:** 🟡 Medium

## Context Gates

- **Architecture** (`.ai-factory/ARCHITECTURE.md`) — **ERROR**: ARCHITECTURE names *both* `src/main.py` and `scripts/*.py` as composition roots, and requires concretes to be wired there. The plan wires the seeder only at `src/main.py` and leaves the `scripts/backfill.py` composition root half-wired (see Critical Issue 1).
- **Rules** (`.ai-factory/RULES.md`) — PASS. File is intentionally empty (no counter-defaults); nothing to enforce.
- **Roadmap** (`ROADMAP.md` 6.2) — PASS. Plan traces to the contract line and its spec; file list, atomic-replace, bare-identity, and canonical-ref gating all match. `Spec:` and format-doc references followed to leaf.
- **skill-context** — none present (`.ai-factory/skill-context/aif-review/SKILL.md` absent); no project overrides to apply.

The design is sound and closely tracks the spec and ground-truth code (the atomic `replace_seed_edges` with `pg_advisory_xact_lock`, the `ON CONFLICT DO NOTHING` config-wins path, bare `push.repo` identity on both endpoints, canonical-ref gating riding `on_push`'s existing early-return). The findings below are a real coverage gap plus two precision issues.

## Critical Issues

### 1. Backfill seeding is a dead path — `scripts/backfill.py` is never wired with a seeder
Task 3 adds `if self._seeder is not None: await self._seeder.seed(...)` to the **end of `backfill`**, and the spec's Change section explicitly requires backfill to seed ("into 3.6's backfill … call `seed(repo, org_id)`"). But `KnowledgeSync.backfill` has exactly **one** caller in the codebase — `scripts/backfill.py:57` — and Task 4 only wires the seeder into `src/main.py`. `scripts/backfill.py` constructs `KnowledgeSync(mirror, indexer, strategy, settings.canonical_refs)` with `seeder` defaulting to `None`, so the offline backfill (the only runnable backfill entrypoint today) silently seeds nothing. `on_push` is fine — it flows through `app.state.knowledge_sync` built in `main.py` — but the backfill guard the spec enumerates is inert.

This is more than a one-line add: `scripts/backfill.py` today creates only the knowledge pool and applies **only** `knowledge/schema.sql`. To wire a working seeder there the implementer must additionally (a) apply `graph/schema.sql`, (b) construct `graph = PgProjectGraph(pool)`, and (c) build `CoordinationSeeder(mirror, graph, settings.canonical_refs)` and pass it to `KnowledgeSync`. None of these steps are in the plan. Note the prior plan revision (`34-6-2-…md`) *did* wire `scripts/backfill.py`; revision 35 dropped it.

**Fix:** Extend Task 4 (or add a task) to wire the seeder into `scripts/backfill.py`'s composition root, including applying `graph/schema.sql` and constructing `PgProjectGraph` there — otherwise remove the backfill claim from the spec's scope, which contradicts the format doc's "re-read … on backfill".

## Issues

### 2. Pipe-split parse instructions ignore the empty boundary cells from leading/trailing `|`
Task 2's `_parse_members` says "split on `|` and strip cells", then "Skip the header row (first cell, lowercased, `== "member"`)" and "`to_repo` = the bare Member cell". A standard table row `| api | contract: x |` splits on `|` into `['', ' api ', ' contract: x ', '']` → stripped `['', 'api', 'contract: x', '']`. Taken literally, the **first cell is the empty boundary cell**, not `member`/`api`, so:
- the header row's first cell is `''` (not `"member"`) → header is **not** skipped and becomes a bogus `root → Member` edge;
- the "Member cell" is ambiguous (index 0 is empty).

The implementer must trim the leading/trailing empty boundary cells first, then treat cell[0] as Member / cell[1] as Relationship. Crucially, trim *only* the boundary empties — a blanket "drop all empty cells" would defeat the very "skip any row whose Member cell is empty" rule the plan requires (an empty-Member row would collapse and mis-map). Since the plan itself flags parsing as a silent-failure surface under test, spell out the boundary-trim so the implementation doesn't route around it. Not fatal (Task 5's parsing tests would eventually catch it), but it invites a plan/implement loop.

### 3. Test list omits the concurrent-seed serialization case the spec enumerates
The plan's Settings block justifies "Testing: yes" with "the spec's Verification section enumerates the cases," and the spec's final Verification bullet is: "Two concurrent `seed` calls for the same repo leave the graph in a consistent end state … never a partial mix." Task 5's test enumeration covers recognition, kind-mapping, other-tables-ignored, replace semantics, and the `replace_seed_edges` contract — but has **no** test exercising the `pg_advisory_xact_lock` serialization, the whole reason Task 1's lock exists. Add at least a two-concurrent-`replace_seed_edges` end-state assertion (against real Postgres) so the atomicity guard is verified, or state explicitly why it is untestable and deliberately skipped.

## Positive Notes
- Ground-truth notes are accurate and load-bearing: `add_edge`'s two-transaction limitation, the `Edge` shape, bare `PushEvent.repo`, `tree`/`default_branch` semantics, and the "no in-repo fake graph" observation all check out against the code.
- `replace_seed_edges` correctly: single acquired connection, `pg_advisory_xact_lock(hashtext($1))` inside `async with conn.transaction()` (xact lock releases on commit, unambiguous int4→bigint overload), `DELETE … source='seed'` only, `ON CONFLICT … DO NOTHING` so a colliding `config` row always wins. Matches `add_edge`'s seed semantics exactly.
- The `seeder` is correctly optional with a `None` default, preserving existing `KnowledgeSync` callers/tests — the ABC addition only needs `PgProjectGraph` implemented, as the plan notes.
- Canonical-ref gating is handled precisely by placing the `on_push` seed call after the existing non-canonical early return; no separate branch check re-implemented.
- No schema migration needed — `replace_seed_edges` reuses the existing `project_edges` table and PK; the plan correctly adds none.

## Deferred observations
- Affects: unknown (future consumer) — The seeder opens a *second* worktree via `mirror.tree(...)` after `backfill`/`on_push` already opened and released one for the same ref. Reclamation is deferred to the next `ensure`, so this at most doubles transient worktree count per canonical push, not a leak. Out of this task's boundary (it is `RepoMirror`'s deferred-reclamation design) and not worth coupling into 6.2; noting only in case a later pass consolidates the two reads.

Overall the plan is close, but Critical Issue 1 leaves a spec-required behavior (backfill seeding) with no runnable path, so it does not pass as written.
