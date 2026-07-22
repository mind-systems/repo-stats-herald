# Plan: 3.1.1 — Mirror isolation & auth contract (red scenarios)

## Context
Define the `RepoMirror`/`GitHubAppAuth` surface (signatures only, stubs raise) and pin its
isolation + single-flight invariants with red concurrency tests, before any git/HTTP logic
exists (3.1.2 turns them green).

## Settings
- Testing: yes
- Logging: minimal
- Docs: no

## Assumptions
- **Guard scope.** The "no git subprocess / no HTTP calls" guard governs *production* code: the
  stubs in `src/github/` shell nothing and open no socket — they only raise. The isolation/cleanup
  tests need a real local git upstream to be green-able unchanged in 3.1.2, so a **test-only** helper
  builds a throwaway local git repo (two branches, differing content). That is scaffolding, not
  production logic; it must succeed (no fixture errors) while the stub calls fail red.
- **Sync surface.** `token()` and `tree()` are synchronous (`tree()` returns a plain
  `AbstractContextManager[Path]`, per the spec) — git worktree work is subprocess-bound and 3.1.2
  will run it off the event loop. Concurrency is therefore exercised with threads
  (`concurrent.futures.ThreadPoolExecutor`), and single-flight is a `threading`-level invariant.
- **No `Settings` change here.** The spec assigns `github_app_id`/`github_app_private_key_path`/
  `mirror_root` to 3.1.2. Stubs take primitives via their constructors; tests construct them directly.
- **Repo identity.** `repo` is the repository *name* (as in `PushEvent.repo`), disambiguated by
  `org_id` — matching the ingestion models already in the tree. The name keys the local bare store
  (`{mirror_root}/{repo}.git`); *where to clone from* is a separate injected seam (below), so the name
  never has to be locally cloneable.
- **Two override seams are pinned here, not in 3.1.2.** The plan's "green unchanged in 3.1.2" promise
  depends on the surface exposing the two points 3.1.2 must redirect. Both are decided in this task:
  - **Clone source.** `RepoMirror`'s constructor takes `clone_source: Callable[[str, int], str]` —
    `clone_source(repo, org_id)` returns a git-cloneable URL/path for that repo. Production (3.1.2)
    wires a function returning the GitHub HTTPS URL (token supplied as git credential by `auth`, never
    in `origin`); tests wire it to the throwaway `local_upstream` path. This is a plain callable, not a
    new named abstraction, so it adds no interface-marker surface — while still giving the isolation/
    cleanup tests a real, offline clone source that 3.1.2 keeps.
  - **Mint step.** `GitHubAppAuth` declares a private `_mint_token(org_id)` seam that `token()` calls
    once under a single-flight lock in 3.1.2. Declaring it on the stub now means the single-flight test
    can bind a counting patch to it *for the right reason* (the seam exists; only the logic is absent).
    3.1.2 must retain this exact method name — a contract this task imposes on spec `04`.
- **`ensure()` precedes `tree()` — they are separate operations.** Per spec `04`, `ensure(repo,
  org_id)` performs the clone/fetch that creates the bare store `{mirror_root}/{repo}.git`, and
  `tree(repo, org_id, ref)` adds a worktree *off that existing store* — it does not clone. So the
  isolation/cleanup tests call `mirror.ensure(repo, org_id)` once before opening any `tree()` context,
  matching the green path in 3.1.2. Against the stub `ensure()` raises `NotImplementedError` first —
  still red for the right reason (logic absent, fixtures clean) and green-able unchanged once 3.1.2
  implements clone-or-fetch. `tree()` never auto-`ensure`s (that would put a fetch behind every
  worktree and contradict `04`'s clone-once/fetch-later separation).
- **`GitHubAppAuth` constructor carries PEM *content*, not a path.** The constructor param is
  `private_key: str` = the loaded PEM text (tests pass `"test-key"`). The composition root in 3.1.2
  reads `github_app_private_key_path` from `Settings`, loads the PEM, and injects the content — keeping
  config-reading at the root and letting the constructor stay side-effect-free (no file read/validate,
  so "constructing must not raise" holds). 3.1.2 must not rename this param or the fixtures break.

## Tasks

### Phase 1: Stub surface

- [x] **Task 1: Create the `github` feature package**
  Files: `src/github/__init__.py`
  Add an empty package marker so `src/github/` is importable alongside the other feature packages.

- [x] **Task 2: Stub `GitHubAppAuth`**
  Files: `src/github/app_auth.py`
  Define a concrete class `GitHubAppAuth` with constructor `__init__(self, app_id: int,
  private_key: str) -> None` storing the two primitives (per the DI/config-injection pattern in
  ARCHITECTURE.md — concretes take primitives, wired at the composition root in 3.1.2). `private_key`
  is the loaded PEM *content* string, not a path (see Assumptions); the constructor must NOT read,
  validate, or otherwise act on it — storing only — so "constructing must not raise" holds. Declare
  two methods, both bodied `raise NotImplementedError`:
  - `def token(self, org_id: int) -> str` — the public surface; in 3.1.2 it returns the cached
    installation token, minting via `_mint_token` at most once per org under a single-flight lock.
  - `def _mint_token(self, org_id: int) -> str` — the private single mint step (App JWT → installation
    token exchange in 3.1.2). It exists on the stub so the single-flight test (Task 7) can bind a
    counting patch to a real attribute; **3.1.2 must retain this exact method name** as the one place a
    mint happens (a contract this task imposes on spec `04`).
  No JWT, no httpx, no imports beyond typing. One-line class docstring stating the intended contract
  (App JWT → per-org installation token, single-flight per org, cached) as behavior, no plan/roadmap
  references.

- [x] **Task 3: Stub `RepoMirror`** (depends on Task 2)
  Files: `src/github/mirror.py`
  Define a concrete class `RepoMirror` with constructor `__init__(self, mirror_root: Path, auth:
  GitHubAppAuth, clone_source: Callable[[str, int], str]) -> None` storing all three (the per-repo bare
  object store lives at `{mirror_root}/{repo}.git`; `auth` supplies the git credential in 3.1.2;
  `clone_source(repo, org_id)` resolves the repo name to a git-cloneable URL/path — the seam tests
  point at `local_upstream` and production points at github.com, see Assumptions). Import `Callable`
  from `collections.abc`. The constructor stores only — it must NOT call `clone_source`, `auth`, or
  touch the filesystem — so constructing must NOT raise. Add:
  - `def ensure(self, repo: str, org_id: int) -> None` — body `raise NotImplementedError`.
  - `def tree(self, repo: str, org_id: int, ref: str) -> AbstractContextManager[Path]` — body
    `raise NotImplementedError` (raising on the `tree(...)` call itself is correct; a `with` around it
    surfaces the same red failure).
  Import `Path` from `pathlib` and `AbstractContextManager` from `contextlib`. No `subprocess`, no
  `git`, no httpx. Class docstring describes the intended behavior (worktree-per-operation off one
  per-repo bare object store at a pinned ref, torn down on exit) as behavior — no plan references.

### Phase 2: Red concurrency tests

- [x] **Task 4: Test package + fixtures** (depends on Task 3)
  Files: `tests/github/__init__.py`, `tests/github/conftest.py`
  Add the test package marker and a `conftest.py` providing, following the existing
  `tests/conftest.py` fixture style:
  - `local_upstream` — a fixture that builds a throwaway local git repo in `tmp_path` with two
    branches whose working trees hold **distinguishable** content (different file bytes per branch);
    yields its path and the two ref names. Test scaffolding only. **Determinism (no ambient config):**
    this is the repo's first git-building fixture, so it must not lean on the developer's global git
    config — else a fresh CI/container surfaces a *fixture error*, which spec `41` forbids.
    - Pin committer identity per commit explicitly — `git -c user.name=herald-test -c
      user.email=herald@test.invalid commit …` (or `GIT_AUTHOR_*`/`GIT_COMMITTER_*` env) — never a bare
      `git commit` (fails `Author identity unknown` without global `user.name`/`user.email`).
      Consider `git init -q` and pin the branch name so `init.defaultBranch` can't leak.
    - Create both branches deterministically (`git checkout -b <name>`) and **yield the ref names**;
      tests drive off the yielded names, never a hardcoded `"main"`/`"master"` (which varies by git
      version / `init.defaultBranch`).
  - `mirror` (depends on `local_upstream`) — constructs `RepoMirror(mirror_root=tmp_path / "mirror",
    auth=GitHubAppAuth(app_id=1, private_key="test-key"), clone_source=lambda repo, org_id:
    str(local_upstream_path))` — the `clone_source` seam resolves any repo name to the local upstream,
    so 3.1.2's `ensure()`/`tree()` clone offline from it unchanged. Constructing must succeed (no method
    runs at construction).
  - `auth` — constructs a bare `GitHubAppAuth(app_id=1, private_key="test-key")` (PEM content, per
    Assumptions).
  Add a module docstring mirroring `tests/ingestion/test_webhook_contract.py`: these tests are red
  against the stubs and must fail because the logic is absent, never on an import or fixture error.

- [x] **Task 5: Isolation red test** (depends on Task 4)
  Files: `tests/github/test_mirror_isolation.py`
  Pin the isolation invariant: two concurrent `mirror.tree(repo, org_id, ref)` calls for the **same
  repo at different refs** each yield their OWN worktree `Path` at their OWN ref's content, and
  neither observes the other's checkout — before or after either completes. Call `mirror.ensure(repo,
  org_id)` once first (the bare store `tree()` checks out from must exist — see Assumptions), then
  structure with a `ThreadPoolExecutor` running two `with mirror.tree(...)` bodies that read their yielded tree's
  content and cross-check that the other ref's content is absent; assert the two yielded paths are
  distinct directories that exist independently. Against the stub `ensure()` (or, if reordered,
  `tree()`) raises `NotImplementedError` first, so the assertions are unreachable and the test is red —
  but the fixtures resolve cleanly. (3.1.2's clone-or-fetch `ensure` + worktree-per-operation `tree`
  makes it green.)

- [x] **Task 6: Cleanup-safety red test** (depends on Task 4)
  Files: `tests/github/test_mirror_isolation.py`
  Pin the cleanup invariant: one operation's `tree()` teardown does not disturb a concurrent
  operation's still-open worktree. Call `mirror.ensure(repo, org_id)` once first (same precondition as
  Task 5), then open two overlapping `tree()` contexts for the same repo; exit (tear down) the first
  while the second is still open, then assert the second's tree still exists and still reads its own
  ref's content. Red against the stub for the same reason as Task 5 (`ensure()` raises first); may
  share the file/fixtures with Task 5 but is a distinct test function so the scenario is separately
  pinned.

- [x] **Task 7: Single-flight token red test** (depends on Task 4)
  Files: `tests/github/test_app_auth_single_flight.py`
  Pin the single-flight invariant: N concurrent `auth.token(org_id)` calls near/after expiry result in
  exactly ONE underlying mint, with all callers receiving the same fresh token. Count mints without
  real crypto/HTTP by `monkeypatch.setattr(auth, "_mint_token", counting_mint)` — the `_mint_token`
  seam declared on the Task 2 stub already exists, so the patch binds cleanly (no `raising=False`, no
  setup/`AttributeError`). `counting_mint` increments a counter and returns a fixed token string.
  **Arity:** `monkeypatch.setattr(auth, "_mint_token", …)` installs an *instance* attribute (unbound),
  so 3.1.2's `self._mint_token(org_id)` calls it *without* `self` — define `def counting_mint(org_id)`
  (or a closure over the counter), NOT `def counting_mint(self, org_id)`, or 3.1.2's green run breaks
  on a `self`/arity mismatch. Guard the counter with a `threading.Lock` (N threads increment it). The test must FORCE the
  concurrent callers to overlap while a mint is in flight, otherwise it cannot tell a correct
  single-flight `token()` from a naive per-request mint that only *usually* double-mints — with an
  instantaneous `counting_mint` the GIL makes the check-then-mint window nondeterministic, so a broken
  impl could intermittently pass `mint_count == 1`. Two synchronization pieces make the assertion
  discriminate:
  - The N worker threads rendezvous at a `threading.Barrier(N)` in **test code**, immediately before
    each calls `auth.token(org_id)`, so all N contend simultaneously. The barrier is in the test body,
    NOT inside `counting_mint` — a correct single-flight calls the mint from exactly one thread, so an
    N-party barrier inside the mint would hang forever.
  - `counting_mint` blocks briefly (a short `sleep`, or wait on a small event) to widen the in-flight
    window. A correct `token()` runs that delay once (the other N-1 pile up on the single-flight lock)
    → `mint_count == 1`; a naive `token()` lets all N enter the mint during the window →
    `mint_count == N` → the assertion fails, which is the regression this test must catch.

  Fire the N `token(org_id)` calls via `ThreadPoolExecutor`, then assert `mint_count == 1` and
  `len(set(results)) == 1`. Against the stub `token()` raises `NotImplementedError` before ever calling
  `_mint_token`, so `mint_count` stays 0 and `results` are exceptions — both assertions fail, red for
  the right reason (token logic absent, fixtures/patch/barrier bound fine). 3.1.2's single-flight
  `token()` wrapping the retained `_mint_token` greens it. Keep the assertions on the observable
  contract (single mint, shared token), not on stub internals.
