## Plan Review Summary

**Plan:** 20.2.1 — Concurrency contract for the async mirror (red scenarios)
**Files Reviewed:** plan + governing spec (`.ai-factory/specs/66-repo-mirror-concurrency-contract.md`), `src/github/mirror.py`, `tests/github/conftest.py`, `tests/github/test_mirror_isolation.py`, `tests/github/test_mirror_credentials.py`
**Risk Level:** 🟢 Low

### Context Gates
- **Architecture** (`.ai-factory/ARCHITECTURE.md`): PASS. Task is test-only. The `GatedRunner` helper is a test-only wrapper injected through `RepoMirror`'s existing `run` seam (the same injectable-`run` idiom `_RecordingRunner` already uses) — it wires a concrete at the test's composition point without touching `src/`. No boundary violation.
- **Rules** (`.ai-factory/RULES.md`): Present but intentionally empty (no counter-defaults). No conflict.
- **Roadmap** (`.ai-factory/ROADMAP.md`): PASS. Plan traces to the `[ ] 20.2.1` contract line, whose `Spec:` names `66-repo-mirror-concurrency-contract.md`. The four scenarios in the plan map one-to-one onto the four invariants named in both the contract line and the spec's *Change* section. Guards (no `src/` change, no synchronization mechanism chosen, `GitHubAppAuth` lock out of scope, red-only-by-construction is legitimate) are all carried forward faithfully.

### Ground-truth verification
Every codebase claim in the plan was checked against the files:
- `ensure` clone-then-fetch branch with no lock around `bare_path.exists()` → confirmed (`mirror.py:108–131`); `_run_git` uses `check=True` and `capture_output=True` (`mirror.py:205`), so a losing second `clone --mirror` into a non-empty dir raises `CalledProcessError` exactly as Task 2 relies on.
- `_finished_worktrees` list appended under `_finished_worktrees_lock` in `tree`'s `finally` (`mirror.py:162–163`); `_reclaim_finished_worktrees` snapshots+clears under the same lock, then runs `worktree remove` outside it (`mirror.py:165–182`) — both critical sections are pure-Python with no git subprocess inside the lock, exactly as Task 3 states.
- `git worktree prune` at `mirror.py:131`; `tree`'s `git worktree add --detach` at `mirror.py:155–158` — line references in Tasks 4/5 are accurate.
- Runner recording shape (`call[0][0][1] == "clone"`) and the injectable `run` idiom match `_RecordingRunner` in `test_mirror_credentials.py`.
- Stale header docstrings confirmed: `conftest.py:1–6` and `test_mirror_isolation.py:1–8` both still describe the pre-implementation stub era ("red against the stubs", "`NotImplementedError`"), so Tasks 1 and 6 are correcting real staleness.
- All referenced fixture/test files exist (`conftest.py`, `test_mirror_isolation.py`, `test_mirror_credentials.py`, `test_mirror_lifecycle.py`).

The argv-matching design is sound: `_run_git` dispatches `["git", <subcommand>, …]`, so gating on the second element (`clone`) and on `("worktree", "add")` / `("worktree", "prune")` pairs distinguishes the three `worktree` subcommands correctly.

The Task 2 deadlock analysis is correct and notably careful: today both threads pass `exists() == False` and both reach the gated `clone`, so `Barrier(2)` releases — no hang today — while the plan explicitly refuses to promise the harness survives 20.2.2 unchanged and defers gate relaxation to the conversion task, matching the spec's red-only-by-construction guard.

### Critical Issues
None.

### Minor Issues

- **Extend the "no plan-layer identifiers in docstrings" guard to all four scenario docstrings, not just the module header (Task 6).** The global documentation rule is absolute: no test comment or docstring may carry a phase/note number (`20.2.2`, `3.1.1`, etc.). Task 6 correctly reminds the implementer of this for the *module header* docstring, but Tasks 2–5 each instruct the implementer to "document this status and reason in the test docstring" and to "record … that the forcing harness … is expected to change at conversion time" — while the plan's own prose refers to "20.2.2" and "3.1.1" throughout. There is a real risk the implementer transcribes those identifiers into the per-test docstrings. Recommend the plan state once, up front, that *every* docstring added or edited (module header and all four scenarios) describes behavior in prose and names no phase/note/roadmap identifier — e.g. "the async conversion" / "the follow-up that makes the git methods awaitable" instead of "20.2.2", and "the torn-tree isolation contract" instead of "3.1.1". Fixable within the task's file boundary.

### Positive Notes
- The plan is unusually honest about harness limits and does not paper over them: Task 3 explicitly states the `GatedRunner` cannot force the append/snapshot-clear to interleave (both sit under the same pure-Python lock with no subprocess inside) and therefore classifies the scenario INAPPLICABLE, using the harness only to run the threads concurrently *around* the locked sections. Task 4 likewise concedes the dangerous window is internal to a single `git worktree add` and cannot be forced from outside. This avoids the trap of asserting a green that the harness cannot actually stress.
- Each scenario instructs the implementer to *run it and record the observed status* rather than assume the expected classification — directly honoring the spec's "state which of the two it is, and why" verification clause.
- Task 2's handling of the losing thread's expected `CalledProcessError` (swallow in the worker; assert the invariant on the shared runner's recorded `clone` count after join, not on whether a worker raised) is exactly right and avoids a flaky which-thread-won dependency.
- Priming steps in Tasks 4 and 5 (a first `ensure` so the bare store exists before any `tree`) correctly reflect that `tree`'s `worktree add --detach` runs against the bare path and cannot open before the clone completes — so the only real overlap to pin is second-`ensure`×`tree`, which the plan states precisely.

## Deferred observations
- Affects: 20.2.2 (the async conversion) — Task 3's consistency assertion ("no finished worktree dropped without removal; none removed twice or while open") is necessarily a coarse end-state check, since a double `worktree remove` is swallowed by `contextlib.suppress(CalledProcessError)` in `_reclaim_finished_worktrees` and cannot surface as a test failure through the current mirror surface. This is a property of the production code being pinned, not a plan defect, and lies outside this test-only task's boundary. When 20.2.2 introduces the real interleaving, it is worth confirming the preserved invariant is observable through a stronger signal than final disk/list state.

The plan is architecturally sound and faithful to the spec; the single minor issue above (uniform no-identifier guard across all four scenario docstrings) is a small correction within the task's boundary — address it and the plan is ready to implement.
