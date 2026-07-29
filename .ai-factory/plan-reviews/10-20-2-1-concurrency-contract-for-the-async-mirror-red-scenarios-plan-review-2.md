## Plan Review Summary

**Plan:** 20.2.1 — Concurrency contract for the async mirror (red scenarios)
**Files Reviewed:** plan + governing spec (`.ai-factory/specs/66-repo-mirror-concurrency-contract.md`), ROADMAP contract line for 20.2.1/20.2.2, `src/github/mirror.py`, `tests/github/conftest.py`, `tests/github/test_mirror_isolation.py`, `tests/github/test_mirror_credentials.py`, and prior review (`…-plan-review-1.md`)
**Risk Level:** 🟢 Low

### Context Gates
- **Architecture** (`.ai-factory/ARCHITECTURE.md`, present): PASS. The task is test-only. `GatedRunner` is a test-only wrapper injected through `RepoMirror`'s existing `run` seam — the same injectable-`run` idiom `_RecordingRunner` already uses in `test_mirror_credentials.py`. It wires a concrete at the test's composition point without touching `src/`. No boundary or dependency-direction violation.
- **Rules** (`.ai-factory/RULES.md`, present): PASS. The file is intentionally empty (a note explaining the project surfaced no counter-default). No conflict.
- **Roadmap** (`.ai-factory/ROADMAP.md`): PASS. The plan's `# Plan:` heading matches the `[ ] 20.2.1` contract line, whose `Spec:` names `66-repo-mirror-concurrency-contract.md`. The plan's four scenarios map one-to-one onto the four invariants named in both the contract line and the spec's *Change* section. All guards (no `src/` change, no synchronization mechanism chosen, red-only-by-construction is legitimate, `GitHubAppAuth`'s per-org lock out of scope) are carried forward faithfully.

### Ground-truth verification
Every codebase claim in the plan was checked against the files and holds:
- `ensure`'s `if not bare_path.exists(): clone --mirror else fetch`, then `_reclaim_finished_worktrees`, then `git worktree prune`, with no lock around the check-then-clone — confirmed (`mirror.py:108–131`).
- `_run_git` funnels every shell-out through the injectable `self._run` with `check=True, capture_output=True` (`mirror.py:190–205`), so a losing second `clone --mirror` into a now-non-empty destination raises `CalledProcessError` exactly as Task 2 relies on.
- `tree` appends `(bare_path, scratch)` under `_finished_worktrees_lock` in its `finally` (`mirror.py:159–163`); `_reclaim_finished_worktrees` snapshots+clears the list under the same lock, then runs `worktree remove --force` *outside* the lock (`mirror.py:165–182`). Both critical sections are pure-Python with no git subprocess held under the lock — precisely as Task 3 states, and the basis for its INAPPLICABLE classification.
- `git worktree prune` at `mirror.py:131`; `tree`'s `git worktree add --detach … cwd=bare_path` at `mirror.py:155–158`. Line references in Tasks 4/5 are accurate, and the "cannot open a worktree before the clone completes" priming rationale matches `cwd=bare_path`.
- Runner recording shape (`call[0][0][1] == "clone"`) and the injectable-`run` construction idiom match `_RecordingRunner`. `_run_git` dispatches `["git", <subcommand>, …]`, so gating on the second argv element (`clone`, `fetch`) and on `("worktree","add")` / `("worktree","prune")` pairs correctly distinguishes the three `worktree` subcommands (add/prune/remove).
- The `mirror`/`local_upstream`/`auth` fixtures and `_git`/`_commit` helpers exist in `conftest.py`; the `mirror` fixture clones from a plain filesystem path and passes no custom `run` — as described.
- Stale header docstrings confirmed: `conftest.py:1–6` and `test_mirror_isolation.py:1–8` still describe the pre-implementation stub era ("red against the stubs", "`NotImplementedError`", "turn them green unchanged"). Tasks 1 and 6 correct real staleness.

### Prior-review resolution
Plan-review-1 raised a single minor issue: the "no plan-layer identifiers in docstrings" guard was stated only for the module header (Task 6) while Tasks 2–5 each instruct "document … in the test docstring" amid prose full of `20.2.2`/`3.1.1`, risking transcription of those identifiers into per-test docstrings. This revision resolves it: the **Docstring convention** paragraph (lines 24–25) now states once, up front, that *every* docstring this task adds or edits — the conftest header, the module header, and all four scenario docstrings — describes behavior in prose and names no phase/note/roadmap identifier, giving the concrete substitutions ("the async conversion" / "the follow-up that makes the git methods awaitable" for `20.2.2`, "the torn-tree isolation contract" for `3.1.1`). This matches the global documentation rule that no test comment or docstring carries a plan-layer reference. Issue fully addressed.

### Critical Issues
None.

### Positive Notes
- The Task 2 deadlock analysis is correct and unusually careful. Today both threads pass `exists() == False` and both reach the gated `clone`, so `Barrier(2)` releases and there is no hang; the plan explicitly refuses to promise the harness survives the async conversion unchanged and defers gate relaxation to 20.2.2, exactly matching the spec's "red-only-by-construction" guard. The invariant is measured on the shared `GatedRunner`'s recorded `clone` dispatch count evaluated after join — decoupled from which worker raised and from git's own concurrent-clone outcome, so the red is deterministic regardless of how two simultaneous clones into one destination actually resolve.
- The plan is honest about harness limits rather than papering over them: Task 3 concedes the `GatedRunner` cannot force the append and the snapshot-clear to interleave (both under the same pure-Python lock, no subprocess inside), and uses the harness only to run the threads concurrently *around* the locked sections; Task 4 concedes the dangerous window is internal to a single `git worktree add` and cannot be forced from outside. Both classify INAPPLICABLE honestly instead of asserting an unstressable green.
- Each scenario instructs the implementer to *run it and record the observed status with its reason* rather than assume the expected classification — directly honoring the spec's "state which of the two it is, and why" verification clause.
- Priming steps in Tasks 3–5 (a first `ensure` so the bare store exists before any `tree`) correctly reflect that `worktree add --detach` runs with the bare path as cwd and cannot open before the clone finishes, so the only real overlap to pin is a *second* `ensure` × `tree`.

## Deferred observations
- Affects: 20.2.2 (the async conversion) — Task 3's consistency assertion ("no finished worktree dropped without removal; none removed twice or while open") is necessarily a coarse end-state check, because a double `git worktree remove` is swallowed by `contextlib.suppress(CalledProcessError)` in `_reclaim_finished_worktrees` (`mirror.py:175`) and cannot surface as a test failure through the current mirror surface. This is a property of the production code being pinned, not a plan defect, and lies outside this test-only task's file boundary. When 20.2.2 introduces the real coroutine interleaving, it is worth confirming the preserved invariant is observable through a stronger signal than final disk/list state.

PLAN_REVIEW_PASS
