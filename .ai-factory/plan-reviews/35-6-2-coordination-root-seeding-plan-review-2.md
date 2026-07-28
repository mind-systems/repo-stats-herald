# Plan Review: 6.2 — Coordination-root seeding (round 2)

**Plan:** `.ai-factory/plans/35-6-2-coordination-root-seeding.md`
**Spec:** `.ai-factory/specs/10-coordination-root-seeding.md` (contract line: ROADMAP.md 6.2)
**Format contract:** `docs/behavior/coordination-root-format.md`
**Files Reviewed:** plan + spec chain + target code (`src/graph/store.py`, `src/graph/models.py`, `src/graph/schema.sql`, `src/knowledge/sync.py`, `src/github/mirror.py`, `src/main.py`, `scripts/backfill.py`, `src/core/config.py`, `src/core/db.py`, `tests/graph/*`)
**Risk Level:** 🟢 Low

## Context Gates

- **Architecture** (`.ai-factory/ARCHITECTURE.md`) — **PASS**. Round-1's ERROR (backfill composition root left half-wired) is resolved: Task 4 now wires `scripts/backfill.py` in full — apply `src/graph/schema.sql`, construct `PgProjectGraph(pool)`, build `CoordinationSeeder`, inject into `KnowledgeSync`. Both composition roots (`src/main.py` and `scripts/*.py`) now build and inject the concrete. The new `src/graph/coordination.py` → `src/github/mirror.RepoMirror` and `src/knowledge/sync.py` → `src/graph/coordination.CoordinationSeeder` edges are constructor-injected dependencies on **public classes**, which the dependency rules explicitly permit (feature B depending on A's public class); `sync.py` already imports `RepoMirror` this same way, so there is precedent and no cycle (`coordination.py` imports nothing from `knowledge/`).
- **Rules** (`.ai-factory/RULES.md`) — PASS. File is intentionally empty (no counter-defaults); nothing to enforce.
- **Roadmap** (`ROADMAP.md` 6.2) — PASS. Plan traces to the contract line and its spec; file list (`coordination.py`, `sync.py`, plus the spec-atomicity-justified `store.py`), atomic-replace, bare-`push.repo` identity on both endpoints, config-untouched, canonical-ref gating, and no-fetch guard all match spec and ground-truth code. `Spec:` and format-doc references followed to leaf.
- **skill-context** — none present (`.ai-factory/skill-context/aif-review/SKILL.md` absent); no project overrides to apply.

## Round-1 findings — all resolved

1. **Backfill dead path (was Critical).** Fixed. A ground-truth note now records that `KnowledgeSync.backfill`'s only caller is `scripts/backfill.py:57`, and Task 4 wires the seeder there in full — including applying the graph schema and constructing `PgProjectGraph` (neither existed in that root before). Verified against the current `scripts/backfill.py`, which today applies only `knowledge/schema.sql` and builds no graph; the plan's three added steps (schema apply, `PgProjectGraph`, seeder) are exactly what makes backfill seeding runnable rather than inert.
2. **Pipe-split boundary cells (was Issue).** Fixed. Task 2 now spells out the boundary-trim with a worked example (`['', 'api', 'contract: x', ''] → ['api', 'contract: x']`) and the critical caveat: trim *only* the outer-delimiter empties, never blanket-drop empties, so an empty-Member row still collapses to an empty cell[0] and is skipped rather than mis-mapping. This closes the exact silent-failure the round-1 review identified.
3. **Concurrent-seed serialization test (was Issue).** Fixed. Task 5 now includes a dedicated bullet running two `replace_seed_edges(repo, …)` calls for the same repo concurrently (`asyncio.gather` over the real `PgProjectGraph` on distinct edge sets) and asserting the end state is exactly one full set — never a partial mix or duplicated union. This exercises the `pg_advisory_xact_lock` the whole of Task 1 exists for. (`create_pool` uses asyncpg defaults ≥ 2 connections, so the two calls genuinely hold connections concurrently and hit the lock rather than serializing at the pool.)

## Verification against ground truth

- `replace_seed_edges` design checks out: single acquired connection, `pg_advisory_xact_lock(hashtext($1))` inside `async with conn.transaction()` (xact lock releases on commit; single `int4` from `hashtext` resolves unambiguously to the `bigint` overload), `DELETE … source='seed'` only, `INSERT … ON CONFLICT (from_repo, to_repo, kind) DO NOTHING` so a colliding `config` row always wins — mirroring `add_edge`'s seed path exactly. No schema migration needed; the existing `project_edges` table and PK are reused.
- Kind mapping (first token after splitting on whitespace and `:`, lowercased → `contract`/`auth`/else) matches the format doc's "first word selects the kind; anything after is descriptive detail." `source="seed"` on every edge; bare identity on both endpoints (`from_repo=repo`, `to_repo=member`) matches the format doc and `PushEvent.repo`'s bare form.
- `seed`'s canonical-ref resolution mirrors `KnowledgeSync._canonical_ref` (`_canonical_refs.get(repo)` → `mirror.default_branch(repo)` fallback); the plan correctly flags the small, unavoidable duplication (the spec fixes `seed(repo, org_id)`'s signature, so it cannot receive a pre-resolved ref). Reading `CLAUDE.md` via `mirror.tree(...)` with no `ensure`/fetch honors the no-network-fetch guard, since `backfill`/`on_push` both call `mirror.ensure(...)` before reaching the seed call.
- Canonical-ref gating is handled by placement: the `on_push` seed call sits after the existing non-canonical early return, so a feature-branch push returns before seeding — the spec's "feature branch never re-seeds" holds by construction, no re-implemented branch check. `seed` runs on every canonical push regardless of whether `CLAUDE.md` changed, which is the intended idempotent re-read the format doc's lifecycle section describes.
- The `seeder` is optional (`None` default), preserving existing `KnowledgeSync` callers/tests; adding an abstract method to `ProjectGraph` only requires implementing it in `PgProjectGraph` (no in-repo fake exists — confirmed against `tests/graph/conftest.py`, which fixtures the concrete store against live Postgres).

## Test scoping is deliberate and correct

The plan's Settings block scopes tests to the silent-failure surfaces (parsing, recognition, kind-mapping, atomic replace, concurrency), per the project's test-philosophy. The spec's "feature-branch does not re-seed" Verification bullet is satisfied structurally — seeding rides the same early-return that already gates indexing — and is not made into a unit test. This is consistent with the codebase: `KnowledgeSync` has **no** unit tests at all (there is no `tests/knowledge/test_sync.py`; the existing `on_push` gate is likewise unverified by any test), so introducing a sync-level seeder-gating test would break, not follow, established convention. The plan documents the gating rationale in Task 3, which is the right treatment for a fail-loud/structural surface. No finding here.

## Positive Notes

- Ground-truth notes are accurate and load-bearing: the `add_edge` two-transaction limitation that motivates `replace_seed_edges`, the `Edge`/`EdgeKind` shape, bare `PushEvent.repo`, `tree`/`default_branch` requiring a pre-existing bare clone, `backfill`'s single caller, and the "no in-repo fake graph" observation all check out against the code.
- The revision is surgical: it fixed exactly the three round-1 findings without disturbing the parts that were already correct, and the backfill fix correctly recognized it was more than a one-liner (schema + graph construction, not just an argument pass-through).

## Deferred observations

- Affects: unknown (RepoMirror deferred-reclamation design, outside this task's boundary) — `seed` opens a *second* worktree via `mirror.tree(...)` after `backfill`/`on_push` already opened and released one for the same ref. Reclamation is deferred to the next `ensure`, so this at most doubles transient worktree count per canonical push — bounded, not a leak. `seed(repo, org_id)`'s signature is fixed by the spec, so it cannot receive the caller's already-open tree; consolidating the two reads would be a `RepoMirror`/signature change beyond 6.2. Noted only in case a later pass unifies the reads.

The revision resolves every round-1 finding, tracks the spec and ground-truth code precisely, and introduces no new architectural, migration, path, or API defect.

PLAN_REVIEW_PASS
