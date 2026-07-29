# Test Plan: RepoMirror — credential handling

## Context
`RepoMirror` (`src/github/mirror.py`) mints an installation token only for `http`/`https` clone sources and carries it as an `http.extraHeader` through `GIT_CONFIG_*` env vars — never through argv, the persisted `origin`, or a raised failure. The fixtures clone from a filesystem path, so this credential branch has never been exercised. This plan covers the plan's credential group only (cases 32–36 of `.ai-factory/specs/78-repo-mirror-surface-test-plan.md`); the lifecycle group is a separate, already-completed entry (`tests/github/test_mirror_lifecycle.py`).

## Settings
- Testing: yes
- Logging: minimal
- Docs: no

## Test Command
`uv run pytest tests/github/test_mirror_credentials.py`

## Target Spec File
`tests/github/test_mirror_credentials.py`

## Tasks

### Phase 1: Persisted-remote safety — real run against `local_upstream`

- [x] **Task 1: token never lands in the bare store's persisted config (case 32)**
  Files: `tests/github/test_mirror_credentials.py`
  Reuse the shared `mirror` / `local_upstream` / `auth` fixtures and the default runner — this is a real `ensure` against the filesystem upstream, not a recorder. The clone source is a plain path, so no token is minted here; the test pins that the persisted remote stays clean regardless.
  Test cases:
  - `should keep remote.origin.url equal to the plain upstream path after ensure` — after `ensure(REPO, ORG_ID)`, assert `git -C <bare> config --get remote.origin.url` equals `str(local_upstream.path)` exactly, where `<bare>` is `object_store_path(REPO)`.
  - `should write no Authorization header or x-access-token string into the bare store's config file` — read the raw text of `<bare>/config` and assert it contains neither `Authorization` nor `x-access-token`.

### Phase 2: Token travels through the environment, not argv — recording runner

- [x] **Task 2: https clone passes the token only via GIT_CONFIG_* env (case 33)**
  Files: `tests/github/test_mirror_credentials.py`
  Build a local `RepoMirror` (do not edit the shared fixture) with `clone_source` returning an https URL, `auth.token` monkeypatched to return `"ghs_SECRET"`, and `run=` set to a recording callable that appends each `(args, kwargs)` and **returns a `subprocess.CompletedProcess`** (guard: `default_branch` reads `.stdout` off the return; a recorder returning `None` fails looking like a mirror bug). Call `ensure`, then inspect the recorded clone invocation.
  Test cases:
  - `should keep the token out of every argv element on the clone invocation` — assert no element of the recorded `["git", ...]` args list contains `"ghs_SECRET"`.
  - `should carry no userinfo in the clone URL` — assert the source URL argument contains no `user:pass@` / `x-access-token@` userinfo.
  - `should pass exactly one GIT_CONFIG entry naming http.extraHeader in env` — assert the recorded `env` carries `GIT_CONFIG_COUNT == "1"` and `GIT_CONFIG_KEY_0 == "http.extraHeader"`.
  - `should encode the token as a base64 Authorization Basic value in GIT_CONFIG_VALUE_0` — assert `GIT_CONFIG_VALUE_0 == f"Authorization: Basic {base64('x-access-token:ghs_SECRET')}"`. Assert on these specific keys, never dict-equality on `env` (it merges `os.environ`, so an ambient `GIT_CONFIG_COUNT` in the developer's shell would otherwise collide).

- [x] **Task 3: the credential is carried on the fetch path too, not only clone (case 34)**
  Files: `tests/github/test_mirror_credentials.py`
  Same recording-runner setup. **Do not "run `ensure` twice" to reach the fetch branch — that is a trap:** the recording runner never actually runs git, so the bare directory is never created on disk, `bare_path.exists()` stays false, and a second `ensure` re-takes the *clone* branch (whose assertions still pass — proving nothing). Instead, **pre-create the bare path** before a single `ensure`, e.g. `local_mirror.object_store_path(REPO).mkdir(parents=True)`, so `bare_path.exists()` is true and `ensure` takes the `else:` `fetch --prune origin` branch. Then inspect the recorded fetch invocation. A token dropped only on clone fails silently for public repos and only bites private ones — both branches must carry it.
  Test cases:
  - `should keep the token out of every argv element on the fetch invocation` — assert no fetch-args element contains `"ghs_SECRET"`.
  - `should carry the same GIT_CONFIG http.extraHeader env on the fetch invocation` — assert the fetch call's `env` carries `GIT_CONFIG_COUNT == "1"`, `GIT_CONFIG_KEY_0 == "http.extraHeader"`, and the base64 `GIT_CONFIG_VALUE_0` for `ghs_SECRET`.

### Phase 3: No token minted for non-http(s) sources — `_credential_for`

- [x] **Task 4: a filesystem source never mints a token (case 35, real-run half)**
  Files: `tests/github/test_mirror_credentials.py`
  Reuse `mirror` / `local_upstream`, but replace `auth.token` with a callable that raises if called. `ensure(REPO, ORG_ID)` against the filesystem upstream must succeed, proving the credential branch was never entered.
  Test cases:
  - `should not consult auth.token when the clone source has no http(s) scheme` — `ensure` completes without raising even though `auth.token` would raise if reached.

- [x] **Task 5: `_credential_for` returns a token only for http(s) schemes (case 35, table half)**
  Files: `tests/github/test_mirror_credentials.py`
  Call `_credential_for` directly with `auth.token` monkeypatched to a known sentinel token; table-check across schemes. The bare store need not exist — this exercises pure scheme dispatch.
  Test cases:
  - `should return None for a plain filesystem path` — e.g. `str(local_upstream.path)` → `None`.
  - `should return None for a file:// source` — `None`.
  - `should return None for an ssh:// source` — `None`.
  - `should return None for a scp-style git@github.com:acme/x.git source` — `None`.
  - `should return the minted token for an http:// source` — returns the sentinel.
  - `should return the minted token for an https:// source` — returns the sentinel.

### Phase 4: Token absent from the raised failure — recording runner via real git failure

- [x] **Task 6: a failing credentialed git command does not leak the token in its exception (case 36)**
  Files: `tests/github/test_mirror_credentials.py`
  Build a local `RepoMirror` with `clone_source` returning `https://127.0.0.1:1/x.git` (connection refused immediately — no real network) and `auth.token` monkeypatched to `"ghs_SECRET"`; use the **default** `subprocess.run` so a real `CalledProcessError` is produced. Call `ensure` and capture the raised `subprocess.CalledProcessError`.
  Test cases:
  - `should raise subprocess.CalledProcessError when the credentialed clone fails` — assert the exception type only (never git's stderr wording, which drifts between versions).
  - `should keep the token out of the exception's str, cmd, stdout, and stderr` — assert `"ghs_SECRET"` appears nowhere across the four attributes, **respecting each one's actual type**:
    - `str(exc)` — `str`; assert `"ghs_SECRET" not in str(exc)`. (`CalledProcessError.__str__` renders only `cmd` + returncode, which carry no token — this is a belt-and-braces check.)
    - `exc.cmd` — `list[str]`; a plain `in` catches only an exact-element match, so join first: assert `"ghs_SECRET" not in " ".join(exc.cmd)`.
    - `exc.stdout` / `exc.stderr` — **`bytes`, because `_run_git` calls `run(..., capture_output=True)` with no `text=True`**. A `str`-in-`bytes` test raises `TypeError`; assert against bytes (`b"ghs_SECRET" not in (exc.stderr or b"")`) or decode first (`(exc.stderr or b"").decode(errors="replace")`). Same for `stdout`.

## Notes for the implementer
- Constants `REPO = "example-repo"` and `ORG_ID = 1` live in the test module, matching `tests/github/test_mirror_isolation.py`.
- The `auth` fixture (`GitHubAppAuth(app_id=1, private_key="test-key")`) cannot mint — its key is not a PEM. Every https-path case must monkeypatch `auth.token` (or use the recording runner) so nothing reaches `jwt.encode`; a test that reaches `jwt.encode` is mis-set-up.
- The recording runner (cases 33, 34) must return a `subprocess.CompletedProcess` (e.g. `CompletedProcess(args, returncode=0, stdout="")`), since `default_branch` reads `.stdout` off the return value.
- Cases 33, 34, and 36 construct a **local** `RepoMirror` with the recording/real runner rather than monkeypatching `src.github.mirror.subprocess.run`, matching the seam already in place (`RepoMirror(mirror_root, auth, clone_source, run=...)`) — no module patching, no leak into neighbouring tests.
