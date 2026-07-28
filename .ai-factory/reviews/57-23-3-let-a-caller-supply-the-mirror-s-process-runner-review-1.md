# Review: 23.3 — Let a caller supply the mirror's process runner

## Scope
`src/github/mirror.py` — one new keyword-with-default constructor parameter plus rerouting of two `subprocess.run` sites through it. Other staged files are planning artefacts, not code.

## Verification

**Task 1 — constructor parameter.** `run: Callable[..., subprocess.CompletedProcess] = subprocess.run` is added as the final parameter, after `clone_source`, and stored as `self._run`. Existing parameter order is preserved; `Callable` and `subprocess` were already imported. The default is bound to the module-level `subprocess.run` at definition time — a stable function object, correct.

**Task 2 — shared git helper.** `_run_git` now calls `self._run(["git", *args], cwd=cwd, env=env, check=True, capture_output=True)` with every keyword identical to the prior direct call. The credential-in-env construction above it (the `GIT_CONFIG_*` / `Authorization` header) is untouched, so the token still travels in the environment and never reaches argv or the raised `CalledProcessError`.

**Task 3 — default-branch read.** `default_branch` now calls `self._run(...)` preserving `capture_output=True, text=True, check=True` and still reads `result.stdout.strip()`. Both invocation sites share the one seam; none remain direct.

**Call-site compatibility (keyword-with-default guard).** Verified every construction passes the first three arguments positionally and none reach past `clone_source`, so adding a defaulted 4th parameter breaks nothing:
- `src/main.py:88`, `scripts/report.py:88`, `scripts/backfill.py:60`, `scripts/backfill_episodic.py:61`, `scripts/bootstrap.py:43` — all `RepoMirror(Path(settings.mirror_root), auth, clone_source)`.
- `tests/github/conftest.py:73` and `tests/changelog/test_time_window.py:54` — keyword/positional forms, all within the first three params.

## Findings
None. The change is a faithful, minimal parameter addition. Worktree isolation, deferred reclamation, and credential handling are untouched; what git runs and in what order is unchanged — only who invokes it. No type mismatch, no runtime break, no security regression.

REVIEW_PASS
