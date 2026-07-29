# Plan Review — RepoMirror: credential handling

**Plan:** `.ai-factory/plans/70-repomirror-credential-handling.md`
**Governing spec:** `.ai-factory/specs/78-repo-mirror-surface-test-plan.md` (ROADMAP_TESTS.md line 20 — "RepoMirror — credential handling")
**Target under test:** `src/github/mirror.py` (`RepoMirror._credential_for` / `_run_git`)
**Files Reviewed:** plan + `src/github/mirror.py`, `src/github/app_auth.py`, `tests/github/conftest.py`, `tests/github/test_mirror_isolation.py`, `tests/github/test_mirror_lifecycle.py`, spec 78

## Code Review Summary

**Risk Level:** 🟡 Medium

The plan is well-scoped and, on most points, correct: it covers exactly cases 32–36, keeps the lifecycle group out (already landed as `test_mirror_lifecycle.py`), reuses the shared `mirror` / `local_upstream` / `auth` fixtures, and — crucially — adopts the `run=` constructor seam that spec 78's "Case-status changes" section settled on rather than the older module-monkeypatch approach the spec's raw Test-Cases section still describes. The `_credential_for` scheme table (Task 5) is accurate against `urlsplit` behaviour, and the no-token-persisted assertions (Task 1) match how `git clone --mirror <path>` writes `remote.origin.url`.

Two defects would bite the implementer. One produces a **green-but-meaningless** test that never exercises the branch it claims to; the other produces a `TypeError` at assertion time. Both are inside the file this task authors, so both are findings.

### Context Gates
- **Architecture** (`.ai-factory/ARCHITECTURE.md` present): PASS — a test-only addition under `tests/github/`, no module boundaries crossed. No WARN.
- **Rules** (`.ai-factory/RULES.md`): PASS — file is intentionally empty (no project counter-defaults). No applicable rule.
- **Roadmap** (`ROADMAP_TESTS.md` line 20): PASS — plan title, scope ("credential group only; lifecycle is its own entry"), the recording-runner approach, and the "recorder must return a completed-process object" guard all match the contract line. Spec linkage (78) is correct.
- **skill-context** (`.ai-factory/skill-context/aif-review/`): absent — no project-specific review overrides to apply.

### Critical Issues

**1. Task 3 (case 34): "run `ensure` a second time" does not reach the fetch branch under a recording runner — the test would silently re-test clone.**
The recording runner is a no-op that only appends `(args, kwargs)` and returns a `CompletedProcess`; it never actually runs `git`, so the bare directory is **never created on disk**. `ensure` branches on `if not bare_path.exists()` (`src/github/mirror.py:114`). After the first `ensure`, `bare_path` still does not exist, so a second `ensure` takes the **clone** branch again — the `fetch --prune origin` branch never executes. Worse, the assertions would still pass, because a re-clone also carries the credential env — yielding a test that is green while proving nothing about the fetch path, which is the entire point of case 34 ("a token dropped only on clone fails silently for public repos and only bites private ones").

The plan lists two options as if co-equal — "run `ensure` a second time (**or** pre-create the bare path)". Only the second works. The instruction must be narrowed to: **pre-create the bare path** (e.g. `local_mirror.object_store_path(REPO).mkdir(parents=True)`) before a single `ensure`, so `bare_path.exists()` is true and the `else:` fetch branch runs. Drop the "run ensure a second time" alternative — it is a trap.

**2. Task 6 (case 36): `exc.stdout` / `exc.stderr` are `bytes`, so the substring assertions as written raise `TypeError`.**
`_run_git` calls `self._run([...], cwd=cwd, env=env, check=True, capture_output=True)` with **no `text=True`** (`src/github/mirror.py:205`). Captured output is therefore `bytes`, and `CalledProcessError.stdout` / `.stderr` are `bytes`. `"ghs_SECRET" in exc.stderr` (str-in-bytes) raises `TypeError: a bytes-like object is required, not 'str'` — the test errors instead of asserting. The plan should specify a bytes-aware check for these two attributes: compare against `b"ghs_SECRET"`, or decode first (`exc.stderr.decode(errors="replace")`). Note also `exc.cmd` is `list[str]`, so `"ghs_SECRET" in exc.cmd` only catches an exact-element match, not a substring inside an element; prefer `"ghs_SECRET" not in " ".join(exc.cmd)`. (`str(exc)` is fine — `CalledProcessError.__str__` renders only `cmd` + returncode, and `cmd` carries no token.)

### Positive Notes
- **Right seam chosen.** Tasks 2/3/6 build a local `RepoMirror(..., run=recorder)` rather than `monkeypatch.setattr(src.github.mirror.subprocess, "run", ...)`. This matches the seam now in the code (`run` keyword-with-default, `src/github/mirror.py:46`) and spec 78's final decision, and avoids patch leakage into neighbouring tests. Correctly overrides the spec's stale raw-Test-Cases wording.
- **Scheme table is exact.** Task 5's expectations hold against `urlsplit`: a plain absolute path, `file://`, `ssh://`, and the scp-style `git@github.com:acme/x.git` (the `@` disqualifies it as a scheme) all yield a scheme outside `{"http","https"}` → `None`; `http://`/`https://` → the minted token. Matches `_credential_for` (`src/github/mirror.py:184-188`).
- **Persisted-config check is grounded.** Task 1's `remote.origin.url == str(local_upstream.path)` is how `git clone --mirror` records a local path (verbatim, not rewritten to `file://`), and the plain-path source means `_credential_for` returns `None` — so the "clean config" property is genuinely exercised.
- **Ambient-env hazard pre-empted.** Task 2 correctly forbids dict-equality on `env` (it merges `os.environ`) and asserts on the specific `GIT_CONFIG_*` keys — matching the `**os.environ` merge in `_run_git`.
- **Fixture-mint guard carried through.** The plan restates that `auth` cannot mint (key is not a PEM) and every https-path case must monkeypatch `auth.token`, so nothing reaches `jwt.encode`.

## Deferred observations
*(none — both issues are inside the file this task authors and are fixable within its boundary)*
