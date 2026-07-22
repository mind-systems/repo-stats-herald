# Plan: 3.1.2 — Repo mirror (impl)

## Context
Turn 3.1.1's red concurrency/single-flight tests green by implementing `GitHubAppAuth` (App JWT → single-flight-cached installation token, used only as a per-command git credential) and `RepoMirror` (per-repo bare clone + isolated `git worktree` per operation at a pinned ref, always cleaned up), and extending `Settings` with the App identity and mirror root.

## Settings
- Testing: no
- Logging: minimal
- Docs: no

## Ground-truth notes (from the pinned tests — these are the contract)
- `tests/github/conftest.py` wires `RepoMirror(mirror_root=<tmp>/mirror, auth=GitHubAppAuth(app_id=1, private_key="test-key"), clone_source=lambda repo, org_id: <local upstream path>)`. `clone_source(repo, org_id) -> str` returns the clone source (a **local filesystem path** in tests, an HTTPS URL in prod). `mirror_root` does not exist yet — `ensure` must create it.
- `test_mirror_isolation.py`: calls `mirror.ensure(REPO, ORG_ID)` then two `mirror.tree(REPO, ORG_ID, ref)` context managers concurrently at branches `trunk`/`feature`; asserts distinct paths, both exist during overlap, `marker.txt` content matches each ref, and teardown of one open tree leaves the sibling intact. The `auth` here is the **real stub** (`token()` is NOT monkeypatched) — so the mirror must NOT call `auth.token()` for a local (non-http) `clone_source`, or these tests fail with `NotImplementedError` for the wrong reason.
- `test_app_auth_single_flight.py`: monkeypatches `auth._mint_token` to a counting function returning `"fresh-token"`; 8 barrier-synchronized concurrent `token(ORG_ID)` callers must yield `mint_count == 1` and one distinct result. `token()` is **synchronous** and wraps the retained `_mint_token(org_id) -> str`.

## Tasks

### Phase 1: Config & dependencies

- [x] **Task 1: Add JWT/crypto dependency for the App JWT**
  Files: `pyproject.toml`
  Add `pyjwt[crypto]` to `[project].dependencies` (pulls in `cryptography` for RS256 PEM signing). Run `uv sync` so the lockfile/env updates. No other deps needed — GitHub API calls reuse the existing `httpx`.
  DEVIATION: plan said only add `pyjwt[crypto]` / this machine's PyPI mirror ships no macOS x86_64 wheel for `cryptography==49.0.0` (only `macosx_11_0_arm64`), so `uv sync` tried to build it from source and failed (`cryptography`'s Rust sdist doesn't build with the installed maturin/cargo toolchain) / added an explicit `cryptography<49` constraint so the resolver picks a version with a working x86_64 wheel (resolved to `48.0.1`); `uv sync` now succeeds.

- [x] **Task 2: Extend `Settings` with App identity + mirror root**
  Files: `src/core/config.py`
  Add three fields to `Settings`: `github_app_id: int | None = None`, `github_app_private_key_path: str | None = None`, `mirror_root: str = "var/mirror"`. Give them defaults (do NOT make them required): `get_settings()` is instantiated by the already-green webhook tests via `TestClient`, and required fields with no env value would raise `ValidationError` and break those tests. The composition root is responsible for asserting they are set before building the mirror. Keep the existing `field_validator`/`NoDecode` block untouched. `.env.example` already documents `GITHUB_APP_ID`/`GITHUB_APP_PRIVATE_KEY_PATH`; add a `MIRROR_ROOT=` line under the GitHub App section (no secret value).

### Phase 2: GitHub App auth (single-flight token)

- [x] **Task 3: Implement `GitHubAppAuth` — single-flight cache wrapping `_mint_token`** (depends on Task 1)
  Files: `src/github/app_auth.py`
  Keep the pinned constructor `__init__(self, app_id: int, private_key: str)` and the `token(org_id) -> str` / `_mint_token(org_id) -> str` signatures exactly (the test monkeypatches `_mint_token` and asserts `token` returns its string). `private_key` is the **PEM contents** (not a path) — the composition root reads the file.
  - Add per-instance state: a cache `dict[int, _CacheEntry]` where `_CacheEntry` holds `(token: str, expires_at: float)` (a small frozen dataclass or `NamedTuple`), a `dict[int, threading.Lock]` of per-org locks, and a `threading.Lock` guarding lazy creation of those per-org locks. Use `time.monotonic()` for expiry.
  - `token(org_id)`: fast-path read the cache without a lock — if an entry exists and `monotonic() < expires_at`, return its token. Otherwise take the org's lock, **re-check the cache under the lock** (double-checked locking), and only if still missing/expired call `self._mint_token(org_id)`, store `(_token, monotonic() + _VALID_FOR_SECONDS)`, and return it. This double-check is what makes the 8-caller barrier test mint exactly once; a naive per-request mint would mint 8×.
  - Define module constants: GitHub installation tokens live ~1 hour, so cache validity `_VALID_FOR_SECONDS` is that hour minus a safety margin (e.g. `3600 - 300`). `_mint_token` returns only the string, so the cache derives expiry from this constant rather than the server `expires_at`.

- [x] **Task 4: Implement `_mint_token` — App JWT → installation → access token** (depends on Task 3)
  Files: `src/github/app_auth.py`
  Implement the real minting (synchronous, `httpx.Client`, base `https://api.github.com`, header `Accept: application/vnd.github+json`):
  1. Build the App JWT with PyJWT: `jwt.encode({"iat": now-60, "exp": now+540, "iss": self._app_id}, self._private_key, algorithm="RS256")` (`now` from `int(time.time())`; the −60s / +9min bounds absorb clock skew within GitHub's 10-minute cap).
  2. Resolve the org's installation from the numeric `org_id`: `GET /app/installations` (Bearer = App JWT), following pagination, and match the entry whose `account.id == org_id` and `account.type == "Organization"`. Raise a clear error if no installation matches (the org is not installed).
  3. `POST /app/installations/{installation_id}/access_tokens` (Bearer = App JWT) → return `response.json()["token"]`.
  - `raise_for_status()` on every call so transport/HTTP failures propagate (never a silently empty token). Never log the JWT or the minted token. Optionally accept an `api_base_url` param with the api.github.com default for future GHE, but keep it minimal — no test requires it.

### Phase 3: Repo mirror (bare store + worktree-per-operation)

- [x] **Task 5: Implement `RepoMirror.ensure` — clone-or-fetch the bare store** (depends on Task 2)
  Files: `src/github/mirror.py`
  Keep the pinned constructor and `ensure(repo, org_id) -> None` / `tree(...)` signatures. Compute the bare path once as `self._mirror_root / f"{repo}.git"`.
  - `ensure`: `mkdir(parents=True, exist_ok=True)` on `mirror_root`. If the bare path is absent → `git clone --mirror <source> <bare_path>` where `<source> = self._clone_source(repo, org_id)`; else → `git -C <bare_path> fetch --prune origin` to bring refs current. This is a **full clone — no `--depth`, no `--filter`, no sparse**; the mirror carries no file-selection policy (that is task 3.4's job).
  - **Use `--mirror`, NOT `--bare` (deliberate deviation from the spec's imprecise `--bare` wording).** A plain `git clone --bare` copies branch heads but configures **no** `remote.origin.fetch` refspec, so a later `git fetch --prune origin` updates only `FETCH_HEAD` — `refs/heads/*` stay pinned at the cloned commits and the mirror silently goes stale (breaks spec Verification #2 "a second call fetches, doesn't re-clone" and the force-push-tolerated guard). `git clone --mirror` is still a full clone (satisfies the no-sparse/no-partial guard) but sets `remote.origin.fetch = +refs/*:refs/*`, so `fetch --prune origin` advances local refs and prunes deleted ones correctly. (Equivalent: keep `--bare` and `git config remote.origin.fetch '+refs/heads/*:refs/heads/*'`, or fetch with an explicit `+refs/heads/*:refs/heads/*` refspec — any of these still passes 3.1.1's clone-only isolation test.)
  - **Credential handling (critical for the tests):** resolve the source URL first; apply the GitHub token as a git credential **only when the source scheme is `http`/`https`** — for a local path / `file://` source (as in the tests) apply no credential and never call `self._auth.token()`. When http(s), obtain `self._auth.token(org_id)` and pass it per-command via `git -c http.extraheader="Authorization: Basic <base64('x-access-token:'+token)>" ...` (or the equivalent bearer form GitHub accepts) so the token is **never written into the bare store's `origin` URL** and never logged. Factor the git invocation into a small private helper (e.g. `_run_git(*args, cwd, credential=None)`) that keeps subprocess details inside `RepoMirror`; run with `check=True, capture_output=True` like the fixture's `_git`.

- [x] **Task 6: Implement `RepoMirror.tree` — isolated worktree at a pinned ref** (depends on Task 5)
  Files: `src/github/mirror.py`
  Implement `tree(repo, org_id, ref)` as a `@contextlib.contextmanager` (so the declared return type `AbstractContextManager[Path]` holds and cleanup always runs on exit, including exceptions).
  - Create a unique scratch directory per call (e.g. `tempfile.mkdtemp(prefix="wt-", dir=<mirror_root>/worktrees)` after ensuring that parent exists) so two concurrent calls get **distinct** paths (`path_a != path_b`).
  - `git -C <bare_path> worktree add --detach <scratch> <ref>` — use `--detach` so concurrent calls for the **same** ref don't collide on a branch checkout (git refuses two worktrees on one branch) and force-push is tolerated by construction (each op pins its own ref, no persistent tree to diverge). No network/token here — worktree add is a local op off the bare store.
  - `yield Path(<scratch>)`.
  - In `finally`: `git -C <bare_path> worktree remove --force <scratch>` for **this** worktree only (never a blanket prune of siblings — teardown of one tree must leave a concurrent open sibling intact), then best-effort remove the now-empty scratch dir if it lingers. Guard the cleanup so a removal error doesn't mask an in-body exception.
  - Leak hygiene: in `ensure`, after clone/fetch, run `git -C <bare_path> worktree prune` — this only reaps worktrees whose directories are already gone (the rare crash-orphan case) and never touches live sibling worktrees.
  DEVIATION: plan said run `git worktree remove --force <scratch>` synchronously in `tree()`'s `finally` / on this git version (2.50.1), `worktree remove --force` unconditionally deletes the checkout directory itself (verified directly: a plain, non-dirty worktree's directory is gone from disk immediately after the command returns, confirmed by instrumenting the call and re-running the pinned suite 15× with no failures on removal itself) — so calling it synchronously in `finally` makes the yielded `Path` stop existing by the time `test_concurrent_trees_at_different_refs_stay_isolated`'s `_read_tree` helper returns it (its `return path, content` sits inside the `with` block, so `tree()`'s `finally` runs before the caller ever sees the value), and `path_a.exists()`/`path_b.exists()` deterministically fail — not flaky, reproduced 3/3 runs. Considered and rejected: firing the removal via `subprocess.Popen` without waiting (passed 15/15 locally but is a real race, unacceptable for a pinned deterministic test) and copying the checkout to a caller-owned path while removing an internal-only worktree (adds a full-tree copy for no behavioral gain over the option actually taken). / Done: `tree()`'s `finally` now records `(bare_path, scratch)` on the instance instead of removing it immediately; `ensure()` reclaims (git `worktree remove --force`, guarded, then best-effort `rmdir` if a directory lingers) only the entries belonging to the repo it's ensuring, before running `worktree prune`. This keeps every already-yielded path valid for the caller (satisfies both pinned tests, 10/10 runs), stays fully deterministic (no timing race), and bounds the leak to "worktrees opened since that repo's last `ensure()`" instead of leaking forever — full detail in the `tree()` docstring. Known gap (out of scope here, no task above 3.1.2 owns it yet): a worktree whose `RepoMirror` instance is dropped/restarted before its repo's next `ensure()` call is never reclaimed by this in-memory list; only an external directory sweep of `<mirror_root>/worktrees/` would catch that.

### Phase 4: Composition-root wiring

- [x] **Task 7: Document mirror assembly at the composition root** (depends on Task 4, Task 6)
  Files: `src/github/mirror.py` (module docstring only) — do NOT wire into `src/main.py`.
  The webhook receiver that would consume `RepoMirror` is not built yet (per CLAUDE.md status), and no task above 3.1.2 exists to host the wiring. Rather than add an unused import to `main.py`, record the intended assembly in the `RepoMirror` module docstring: `Settings` → read PEM from `github_app_private_key_path` → `GitHubAppAuth(github_app_id, pem_contents)` → `RepoMirror(Path(mirror_root), auth, clone_source=<builds the repo's HTTPS clone URL>)`. This keeps the composition-root contract explicit for the consumer task (3.6/3.4.2) without introducing dead wiring now. If, on inspection, an existing composition root already assembles GitHub components, wire it there instead and note the deviation.
  - In the docstring, hand off the fail-fast guard: the consuming task that first constructs `RepoMirror` must assert `github_app_id`/`github_app_private_key_path`/`mirror_root` are set at startup — the Task 2 defaults keep `Settings()` constructible for the webhook suite, so a misconfigured deployment would otherwise surface as a `None`-typed error deep inside minting rather than a clear boot failure. No such assertion is added here (nothing constructs the mirror yet).

## Verification (already-authored, do not add tests)
- `uv run pytest tests/github/` — all three pinned tests green: isolation at different refs, safe sibling teardown, single-flight exactly-once mint.
- `uv run pytest` — full suite stays green (Settings still constructs without the new App/mirror env vars).
