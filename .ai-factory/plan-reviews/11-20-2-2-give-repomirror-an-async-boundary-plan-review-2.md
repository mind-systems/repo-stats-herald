# Plan Review 2 — 20.2.2 Give `RepoMirror` an async boundary

**Plan:** `.ai-factory/plans/11-20-2-2-give-repomirror-an-async-boundary.md`
**Governing spec:** `.ai-factory/specs/61-repo-mirror-async-boundary.md`
**Files Reviewed:** plan + mirror + every production/script caller + the concurrency suite and pinned scenarios (verified against the current tree)
**Risk Level:** 🟢 Low — the round-1 issue is resolved and an independent re-sweep found nothing new.

## Context Gates

- **Architecture (`.ai-factory/ARCHITECTURE.md`)** — PASS: the offload mechanism stays owned inside `RepoMirror` (infra); no feature gains an `asyncio` concern beyond `await`, and no concrete is wired outside a composition root. Boundaries respected.
- **Rules (`.ai-factory/RULES.md`)** — PASS: no counter-defaults to enforce.
- **Roadmap linkage** — PASS: plan heading matches spec 61 (Phase 20). The plan's `Ground-truth notes` deviations are grounded against the current tree and are conformance, not drift.
- **Skill-context (`aif-review`)** — none present; no project overrides to apply.

## Round-1 issue — resolved

Plan-review 1's single non-blocking issue was that Task 1's method enumeration omitted `_reclaim_finished_worktrees`, which also shells out (`mirror.py:165–182`, called from `ensure` at `:127`). The current plan closes this fully:

- Task 1's headline lists `_reclaim_finished_worktrees` among the members converted to `async def` (line 24).
- A dedicated bullet (line 25) spells out the failure mode a synchronous helper would cause once `_run_git` is a coroutine (unawaited coroutine → no subprocess → `contextlib.suppress` catches nothing → deferred reclamation silently never happens), mandates awaiting each removal, and pins the `ensure` call site change to `await self._reclaim_finished_worktrees(bare_path)`. It also correctly scopes the offload: only the `worktree remove` calls move to the offload thread; the list snapshot/clear under `_finished_worktrees_lock` stays synchronous.

Verified against `mirror.py` — the helper does loop `self._run_git("worktree", "remove", ...)` under `contextlib.suppress(subprocess.CalledProcessError)`, exactly as the plan describes.

## Deviation verification (plan's ground-truth notes vs. code)

Each annotated deviation re-checked against the current tree and holds:

- **Release fan-out lives in `src/delivery/service.py`, not `router.py`.** Confirmed: `ReleaseDelivery.deliver` calls `self._mirror.ensure(...)` at `service.py:81` and `self._versioner.next(...)` at `:83`; `router.py` has no mirror reference. The spec's `Files & types` line for `router.py` is stale post-20.1 — the plan follows the file.
- **Extra callers beyond the spec's list.** All confirmed reachable and covered: `Versioner._next_staging` → `default_branch` (`versioner.py:121`); `resolve_canonical_ref` → `default_branch` from `knowledge/sync.py`, `graph/coordination.py`, `episodic/backfill.py`, `changelog/report.py`, and `scripts/report.py:126`.
- **`object_store_path` stays synchronous.** Confirmed pure path return (`mirror.py:58–68`); its sync consumers (`Versioner`, `TimeWindow`, `EpisodicBackfill`) correctly untouched.
- **`resolve_canonical_ref` becomes `async`.** Correct — it calls `mirror.default_branch` at `mirror.py:218`.
- **`scripts/backfill.py` needs no edit.** Confirmed: it constructs a mirror but makes no direct shelling call (not even `sweep_worktrees`); it only `await sync.backfill(...)`, which drives `ensure`/`tree` internally.

## Independent caller-completeness sweep

Grepped every `ensure` / `tree` / `default_branch` / `sweep_worktrees` / `resolve_canonical_ref` call site across `src/` and `scripts/`. **Every site maps to a task, and every line number in the plan is exact:**

| Call site | Task |
|---|---|
| `versioning/versioner.py:121` (`default_branch`) | 2 |
| `delivery/service.py:81` (`ensure`) + `:83` (`versioner.next`) | 3 |
| `knowledge/sync.py:36,39,43,57,77` | 4 |
| `graph/coordination.py:38,100` | 4 |
| `ingestion/writer.py:39,41` | 5 |
| `episodic/backfill.py:63,66` | 5 |
| `knowledge/bootstrap.py:56,58` | 5 |
| `changelog/report.py:47` | 6 |
| `main.py:89`, `scripts/report.py:89,120,126`, `scripts/bootstrap.py:44`, `scripts/backfill_episodic.py:62` | 7 |
| `mirror.py:218` (`default_branch` inside `resolve_canonical_ref`) | 1 |

Each script/composition-root site already sits inside an `async def _run(...)` driven by `asyncio.run`, so the "no new `asyncio.run`" guard is satisfiable as written.

## Concurrency-suite fidelity

Re-read `tests/github/test_mirror_isolation.py`: exactly six scenarios — two plain torn-tree tests, one RED (`test_two_overlapping_ensures_never_both_take_the_clone_branch`), and three INAPPLICABLE (`test_finished_worktree_bookkeeping_stays_consistent...`, `test_worktree_prune_does_not_race_a_worktree_being_created`, `test_ensure_overlapping_an_open_tree_does_not_disturb_it`). Task 9's split (three INAPPLICABLE + two torn-tree keep their invariants; the RED scenario's two-party barrier is relaxed while the "a clone is dispatched at most once" assertion survives) matches the scenarios' own docstrings, which already state the surviving invariant and that the barrier must be relaxed. With a per-repo `asyncio.Lock` held across `ensure`, `asyncio.gather` of two `ensure` coroutines serializes so only one reaches the clone gate — confirming both the barrier-relaxation need and the surviving assertion.

Verified `asyncio_mode = "auto"` (`pyproject.toml:22`), so converting the mirror suites and `Versioner.next` to `async def` needs no `@pytest.mark.asyncio` markers — consistent with the plan not calling for any. Confirmed the plan-layer citation the plan schedules for scrubbing exists verbatim (`tests/ingestion/conftest.py`: "roadmap 20.2.2 will make it awaitable"), so Task 10's cleanup is grounded.

## Critical Issues

None.

## Positive Notes

- The round-1 completeness gap is fully closed, with the failure mode and both mechanism variants (`_run_git` as `async def` vs. a `_to_thread` unit-offload) reasoned through rather than just name-added.
- The serialization design decision is pinned at the right altitude: a lazily-created per-repo `asyncio.Lock` held across `ensure`, explicitly **not** taken in `tree` (so `ensure`/`tree` overlap stays legal and the two torn-tree + three INAPPLICABLE scenarios keep holding), with the `threading.Lock` around `_finished_worktrees` retained for bookkeeping consistency.
- Guard fidelity is high throughout: credential-env construction and `capture_output=True, check=True` kept verbatim, no new `asyncio.run`, reclamation timing preserved (next `ensure`, never in `tree`'s `finally`), and `object_store_path` / `scripts/backfill.py` pinned as deliberate non-edits.
- Every task line number was checked against the current tree and is exact — the plan will not send the implementer to a stale offset.

PLAN_REVIEW_PASS
