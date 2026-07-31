# Plan Review — 20.2.2 Give `RepoMirror` an async boundary

**Plan:** `.ai-factory/plans/11-20-2-2-give-repomirror-an-async-boundary.md`
**Governing spec:** `.ai-factory/specs/61-repo-mirror-async-boundary.md`
**Files Reviewed:** plan + 20 code/test files across the mirror, its callers, the composition roots, and the affected test suites
**Risk Level:** 🟡 Medium (one completeness gap in the mirror-conversion enumeration; everything else verified sound)

## Context Gates

- **Architecture (`.ai-factory/ARCHITECTURE.md`)** — WARN (informational): the change respects the feature-modular/DI boundaries. The offload mechanism stays owned inside `RepoMirror` (infra), no feature gains an `asyncio` concern beyond `await`, and no concrete is wired outside a composition root. Aligned.
- **Rules (`.ai-factory/RULES.md`)** — PASS: file holds no counter-defaults; nothing to enforce.
- **Roadmap linkage** — PASS: plan heading matches spec 61 (`.ai-factory/specs/61-repo-mirror-async-boundary.md`), which sits in Phase 20. The plan's `Spec vs. code` deviations are grounded against the current tree and are conformance, not drift (see below).
- **Skill-context (`aif-review`)** — none present; no project overrides to apply.

## Deviation verification (plan's ground-truth notes vs. code)

Each annotated deviation was checked against the code and holds:

- **Release fan-out lives in `src/delivery/service.py`, not `src/ingestion/router.py`.** Confirmed: `ReleaseDelivery.deliver` calls `self._mirror.ensure(...)` at `service.py:81` and `self._versioner.next(...)` at `:83`; `router.py` has no mirror reference. Spec's `Files & types` line for `router.py` is stale post-20.1 — the plan correctly follows the file.
- **Extra callers beyond the spec's list.** Confirmed reachable and all covered by the tasks: `Versioner._next_staging` calls `default_branch` (`versioner.py:121`); `resolve_canonical_ref` reaches `default_branch` from `knowledge/sync.py`, `graph/coordination.py`, `episodic/backfill.py`, `changelog/report.py` (`TimeWindow.resolve`), and `scripts/report.py:126`.
- **`object_store_path` stays synchronous.** Confirmed pure path return (`mirror.py:58-68`); its sync consumers (`Versioner`, `SinceDeployWindow`, changelog sections, `EpisodicBackfill`, `TimeWindow`) are correctly left untouched.
- **`resolve_canonical_ref` becomes `async`.** Correct — it calls `mirror.default_branch` (`mirror.py:218`).
- **`scripts/backfill.py` needs no edit.** Confirmed: it constructs a mirror but makes no direct shelling call (it does not even call `sweep_worktrees`); it only `await sync.backfill(...)`. Correct.

## Caller-completeness audit (independent sweep)

Cross-checked every production call site of `ensure` / `tree` / `default_branch` / `sweep_worktrees` / `resolve_canonical_ref` against the task list — all covered (Tasks 2–7). Line numbers in Task 7 verified exact: `main.py:89`, `scripts/report.py:89,120,126`, `scripts/bootstrap.py:44`, `scripts/backfill_episodic.py:62`.

Test-fake sweep across `tests/`: the plan's Task 10 list is complete for fakes that expose `ensure`/`tree`/`default_branch`. The four `FakeMirror`s **not** listed — in `tests/changelog/test_summary_section.py`, `test_per_branch_section.py`, `test_remaining_section.py`, and `test_since_deploy_window.py` — expose only the sync `object_store_path`, so they correctly need no change. `SinceDeployWindow.resolve` reads only `object_store_path` + `collector.list_tags`, so it and its suite are correctly excluded.

Verified `asyncio_mode = "auto"` in `pyproject.toml`, so converting the currently-synchronous mirror suites (`test_mirror_lifecycle`, `test_mirror_credentials`, `test_mirror_isolation`) and the versioner functions to `async def` needs no `@pytest.mark.asyncio` markers — consistent with the plan not calling for any. The `test_mirror_lifecycle.py` header already anticipates a mechanical async conversion, and `test_mirror_isolation.py`'s clone-race docstring already states the surviving invariant is "a clone is dispatched at most once" and that the two-party barrier must be relaxed — Task 9 matches the pinned intent exactly.

## Critical Issues

None blocking.

## Issues

- **Task 1's method enumeration omits `_reclaim_finished_worktrees`, which also shells out.** `mirror.py:165-182` invokes `self._run_git("worktree", "remove", ...)` in a loop, and `ensure` calls it at `mirror.py:127`. The task lists exactly which members change shape (`ensure`, `default_branch`, `sweep_worktrees`, `tree`, `resolve_canonical_ref`, and the `_run_git` helper) but never names `_reclaim_finished_worktrees`. Once `_run_git` becomes `async def` (the plan's first suggested mechanism), a `_reclaim_finished_worktrees` left synchronous would call the coroutine without `await`: no subprocess runs, `contextlib.suppress(subprocess.CalledProcessError)` catches nothing, and the worktree removal silently never happens — breaking the deferred-reclamation timing the spec pins as a guard (only a `RuntimeWarning: coroutine was never awaited` would hint at it). The alternate "thin `_to_thread` around the existing sync body" mechanism has the same requirement — the reclaim loop must run on the offload thread, either as an awaited helper or offloaded as a unit, and `ensure` must `await` it. Recommend adding `_reclaim_finished_worktrees` to Task 1's conversion list (and, if `_run_git` becomes async, noting that the `ensure` call at line 127 becomes `await self._reclaim_finished_worktrees(bare_path)`). The lifecycle/isolation suites that assert reclamation would likely catch a literal-following mistake, but the enumeration should not depend on the test net.

## Positive Notes

- The spec-vs-code reconciliation is thorough and correct: it caught the 20.1 fan-out move, enumerated the callers the spec's `Files & types` omitted, and pinned `object_store_path` / `scripts/backfill.py` as deliberate non-edits — each verifiable against the current tree.
- The serialization design decision is stated at the right altitude: a per-repo `asyncio.Lock` held across `ensure`, explicitly **not** taken in `tree` (so `ensure`/`tree` overlap remains legal and the two torn-tree + INAPPLICABLE scenarios keep holding), with the `threading.Lock` around `_finished_worktrees` retained for the bookkeeping-consistency invariant. This matches what 20.2.1's red scenarios pin.
- Task 9 correctly separates "relax the forcing harness" from "keep the assertion" for `test_two_overlapping_ensures_never_both_take_the_clone_branch`, honoring both the spec's red-only-by-construction guard and the scenario's own docstring.
- Guard fidelity is high: credential-env construction and `capture_output/check` kept verbatim, no new `asyncio.run`, reclamation timing preserved, and the plan-layer citation scrub in `tests/ingestion/conftest.py` is called out per the global doc rules.
