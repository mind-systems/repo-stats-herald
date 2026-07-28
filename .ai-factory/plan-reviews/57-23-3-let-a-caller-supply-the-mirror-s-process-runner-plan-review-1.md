## Plan Review Summary

**Plan:** 23.3 — Let a caller supply the mirror's process runner
**Files Reviewed:** plan + `src/github/mirror.py` (target), governing spec `.ai-factory/specs/83-repo-mirror-process-runner-seam.md`, consumer spec `.ai-factory/specs/78-repo-mirror-surface-test-plan.md`, all construction sites
**Risk Level:** 🟢 Low

### Context Gates
- **Roadmap** — WARN→OK. Contract line `.ai-factory/ROADMAP.md:126` (task 23.3) matches the plan title and names `specs/83-repo-mirror-process-runner-seam.md` as the governing spec. The plan realizes that spec's `## Change` and `## Guards` verbatim (add keyword-with-default runner, route both sites, sequence against 20.2.2). The consumer test plan (spec 78, `## Refactor Required`) demands exactly this API — `RepoMirror(mirror_root, auth, clone_source, run=subprocess.run)` — and the plan produces it. Linkage is clean.
- **Architecture** — OK. The change is textbook for this codebase's stated pattern (constructor dependency injection, "wire concretes only at the composition root"). Injecting the process runner as a keyword-with-default is fully aligned; it makes the seam observable without moving any concrete wiring. No boundary or dependency-direction violation.
- **Rules** — OK. `.ai-factory/RULES.md` is intentionally empty (no counter-defaults). No `aif-review` skill-context file present.

### Critical Issues
None.

### Verification against ground truth
Every concrete claim in the plan was checked against the live file:

- **Task 1** — `RepoMirror.__init__` currently takes `(mirror_root, auth, clone_source)` (mirror.py:41–46). Adding `run` after `clone_source` as keyword-with-default is correct and preserves parameter order. `Callable` is imported from `collections.abc` (line 8) and `subprocess` is imported (line 5), as the plan states. There is no `from __future__ import annotations`, so the annotation is evaluated at class-definition time — `Callable[..., subprocess.CompletedProcess]` is valid under Python 3.12 (`collections.abc.Callable` is subscriptable since 3.9; `subprocess.CompletedProcess` is a real class), so it will not raise. ✔
- **Task 2** — the `_run_git` body ends in `subprocess.run(["git", *args], cwd=cwd, env=env, check=True, capture_output=True)` (mirror.py:203), matching the plan's quoted line character-for-character. Routing it through `self._run(...)` with identical kwargs is a pure who-runs-it change; the credential-in-env construction above it (lines 189–202) is untouched. ✔
- **Task 3** — `default_branch` holds the second direct call `subprocess.run(["git", "symbolic-ref", "--short", "HEAD"], cwd=self._bare_path(repo), capture_output=True, text=True, check=True)` reading `result.stdout.strip()` (mirror.py:77–84), matching the plan exactly. Routing through `self._run` still returns a `CompletedProcess` with `.stdout`, so `text=True` + `.stdout.strip()` continue to work. ✔
- **Single-seam completeness** — these are the *only* two direct `subprocess.run` invocation sites in the module; every other git call (`sweep_worktrees`, `ensure`, `tree`, `_reclaim_finished_worktrees`) already funnels through `_run_git`. So Tasks 2 + 3 genuinely collapse the module to one execution seam, satisfying the spec guard that leaving `default_branch` direct would defeat the point. ✔
- **Unchanged-callers guard** — confirmed all constructions are positional/keyword up to `clone_source`, so a trailing keyword-with-default breaks none: `src/main.py:88`, `scripts/report.py:88`, `scripts/backfill.py:60`, `scripts/backfill_episodic.py:61`, `scripts/bootstrap.py:43` (the "four `scripts/*`" the plan names), and `tests/github/conftest.py:73` (the `mirror` fixture, keyword form). ✔
- **20.2.2 sequencing** — the live `_run_git` is still synchronous (no thread offload), so 20.2.2 (spec 61) has not landed. The plan's described call-site shapes match the current file, and the DEVIATION protocol correctly instructs the implementer to follow the file if that changes. ✔

### Positive Notes
- The plan is scoped exactly to the governing spec — a parameter addition and two call-site rewrites — with no drift into worktree isolation, reclamation timing, or command ordering, matching every guard in spec 83.
- Quoting the exact current call expressions (rather than paraphrasing) makes the edits mechanical and unambiguous, and the DEVIATION note pre-empts the one real collision risk (20.2.2 rewriting the same helper).
- The dependency annotations (`Task 2`/`Task 3` depend on `Task 1`) are correct and the tasks are minimal and non-overlapping.

### Note (non-blocking, no action needed)
The plan's enumeration of unchanged construction sites does not list `tests/changelog/test_time_window.py:54`, which also constructs `RepoMirror(mirror_root, auth, clone_source=lambda …)`. This is not a defect: the plan's governing guarantee — a trailing keyword-with-default leaves every existing positional/keyword construction byte-for-byte unchanged — holds for that site identically, and the plan does not ask to touch it. Recorded only so the implementer isn't surprised to find one more (unaffected) call site than the list names.

PLAN_REVIEW_PASS
