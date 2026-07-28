# Plan: 23.3 — Let a caller supply the mirror's process runner

## Context
Give `RepoMirror` a single, injectable process-execution seam so a caller can pass a recording runner and directly observe the credentialed https clone/fetch path (token in env, absent from argv and from the raised failure) — a guarantee that today produces no return value and cannot be exercised by the filesystem-source fixtures.

## Settings
- Testing: no
- Logging: minimal
- Docs: no

## Tasks

### Phase 1: Single execution seam

- [x] **Task 1: Add the keyword-with-default `run` constructor parameter**
  Files: `src/github/mirror.py`
  In `RepoMirror.__init__` add a final keyword parameter `run: Callable[..., subprocess.CompletedProcess] = subprocess.run` (after `clone_source`, so it is keyword-with-default and every existing positional construction — `src/main.py`, the four `scripts/*` entrypoints, and `tests/github/conftest.py`'s `mirror` fixture — stays byte-for-byte unchanged and keeps using `subprocess.run`). Store it as `self._run = run`. Do not reorder the existing parameters. `Callable` is already imported from `collections.abc`; `subprocess` is already imported.

- [x] **Task 2: Route the shared git helper through the seam** (depends on Task 1)
  Files: `src/github/mirror.py`
  In `_run_git`, replace the direct `subprocess.run(["git", *args], cwd=cwd, env=env, check=True, capture_output=True)` with `self._run(["git", *args], cwd=cwd, env=env, check=True, capture_output=True)`. Keep every keyword argument and its value identical — this is a who-runs-it change only. The credential-in-env construction above the call (the `GIT_CONFIG_*` / `Authorization` env, the argv-avoidance comment) is untouched, so worktree isolation, credential handling, and the raised-failure attributes all stay exactly as they are.

- [x] **Task 3: Route the default-branch read through the same seam** (depends on Task 1)
  Files: `src/github/mirror.py`
  In `RepoMirror.default_branch`, replace the direct `subprocess.run(["git", "symbolic-ref", "--short", "HEAD"], cwd=self._bare_path(repo), capture_output=True, text=True, check=True)` with the same call through `self._run(...)`, preserving every argument (including `text=True`) and still reading `result.stdout.strip()`. This closes the second, separate invocation site so the mirror has one execution seam rather than two — leaving this call direct would defeat the point of the task.

## Notes for the implementer
- **Sequencing against 20.2.2 (spec 61):** that open task rewrites this same `_run_git` body to move its work onto a thread. Whichever lands first, the runner must survive as the *one* seam both sites share — never duplicated per call site. If 20.2.2 is already applied when you implement this, thread the injected `self._run` through the offload rather than adding a second call path.
- **DEVIATION protocol:** if the live `src/github/mirror.py` no longer matches the two call sites described here (e.g. 20.2.2 already landed), follow the file as ground truth, apply the single-seam intent to whatever the current invocation shape is, and annotate the deviation.
- Scope is a parameter addition only: do not alter worktree-per-operation isolation, the deferred worktree-reclamation timing, or anything about what git commands run or in what order.
