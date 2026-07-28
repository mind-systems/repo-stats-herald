# RepoMirror (non-concurrency surface) — Test Plan

**Date:** 2026-07-29
**Source:** roadmap-test-coverage agent

## Source Overview

`src/github/mirror.py` implements `RepoMirror`: one bare object store per repo at `{mirror_root}/{repo}.git`, plus a fresh detached `git worktree` per operation under `{mirror_root}/worktrees/wt-*`, so no operation ever shares a mutable checkout. Its five observable surfaces are `ensure` (clone-if-absent else `fetch --prune`, then reclaim finished worktrees and `worktree prune`), `tree` (context manager yielding a checkout pinned at a ref, whose removal is **deferred to the repo's next `ensure`**), `default_branch` (`git symbolic-ref --short HEAD` in the bare store), `sweep_worktrees` (startup reclamation of everything under the worktrees root + per-bare prune), and `object_store_path` (pure path, the read-only entry point used by changelog/versioning history replay). Credentials never touch argv or the persisted `origin` URL — `_credential_for` mints a token only for `http`/`https` sources and `_run_git` passes it as an `http.extraHeader` through `GIT_CONFIG_*` env vars. The module-level `resolve_canonical_ref` is the single home for the "which ref is this repo canonical on" policy and is included here because it bottoms out in `default_branch`.

## Instantiation

Reuse the three fixtures already in `tests/github/conftest.py` — do not invent new ones:

- **`local_upstream`** — a throwaway git repo at `tmp_path/upstream` standing in for GitHub. Branch `trunk` (`ref_a`) holds `marker.txt == "content-a"`; branch `feature` (`ref_b`) holds `"content-b"`. **Load-bearing detail:** the fixture ends with `git checkout -b feature`, so the upstream's `HEAD` points at `refs/heads/feature` — a `--mirror` clone copies that, which is exactly the "default branch is not `main`" condition the `default_branch` cases need, for free.
- **`auth`** — `GitHubAppAuth(app_id=1, private_key="test-key")`. It cannot actually mint (the key is not a PEM); it never has to, because the mirror's clone source is a filesystem path with no URL scheme, so `_credential_for` returns `None`. Any test that exercises the https path must monkeypatch `auth.token` or `src.github.mirror.subprocess.run`; a test that reaches `jwt.encode` is mis-set-up.
- **`mirror`** — `RepoMirror(mirror_root=tmp_path/"mirror", auth=auth, clone_source=lambda repo, org_id: str(local_upstream.path))`. `mirror_root` does not exist yet, so `ensure`'s `mkdir(parents=True)` is genuinely exercised. The lambda ignores the repo name, so any number of repo names clone from the same upstream. When a case needs two *genuinely different* upstreams, build a local `RepoMirror` inside that test rather than editing the shared fixture.

Constants `REPO = "example-repo"` / `ORG_ID = 1` live in the test module, matching `tests/github/test_mirror_isolation.py`. Simulating a process restart means constructing a **new** `RepoMirror` over the same `mirror_root` — the deferred-reclamation list is in-memory, so a fresh instance is precisely the crash/restart model `sweep_worktrees` exists for.

## Existing Coverage

`tests/github/test_mirror_isolation.py` has exactly two tests, both concurrency-only: `test_concurrent_trees_at_different_refs_stay_isolated` and `test_teardown_of_one_tree_does_not_disturb_a_still_open_sibling`. Nothing covers `ensure`'s clone-vs-fetch branch, force-push, `default_branch`, `sweep_worktrees`, `object_store_path`, `resolve_canonical_ref`, credential handling, missing refs, or the deferred-reclamation timing contract. `tests/github/test_app_auth_single_flight.py` owns the token cache and is out of scope here.

## Test Cases

### `ensure`

1. **should create a bare object store at `{mirror_root}/{repo}.git` when the repo has never been cloned** — assert `mirror_root` did not exist beforehand, exists after, and `rev-parse --is-bare-repository` is `true`.
2. **should fetch into the existing store rather than re-cloning when the bare path already exists** — Setup: after the first `ensure`, drop a sentinel file inside the bare dir, add a new branch + commit upstream, `ensure` again. Assert the sentinel survives **and** the new upstream ref now resolves — both halves are needed; either alone is satisfiable by the wrong implementation.
3. **should adopt upstream's rewritten history when a ref was force-pushed** — Setup: `git branch -f trunk <new-sha>` upstream (avoids checking the upstream out, which the fixture leaves on `feature`); `ensure` again. Non-obvious: a `--mirror` clone's `origin` refspec is `+refs/*:refs/*`, so the force applies without extra flags.
4. **should drop a ref that was deleted upstream** — pins the `--prune` that keeps a stale branch from being indexed as live.
5. **should remove worktrees finished since the last call and leave a still-open one alone** — single-threaded, sequential; not a concurrency case. Open and exit `tree(ref_a)`, open `tree(ref_b)` and keep it open, call `ensure`, assert path A is gone from disk and from `git worktree list --porcelain`, while path B is still readable.
6. **should not reclaim another repo's finished worktrees** — pins that reclamation is keyed by bare path, not global.
7. **should not raise when a finished worktree's directory was already deleted out from under it** — `shutil.rmtree` the scratch dir after the `with` block, then `ensure`.
8. **should create `mirror_root` including missing parents when it does not exist** — point a locally built `RepoMirror` at `tmp_path/"a"/"b"/"mirror"`.

### `tree`

9. **should yield content that is exactly the requested ref's, sequentially for each ref** — the single-threaded counterpart to the existing concurrency tests, and the direct guard against the plausible-but-stale-content hazard.
10. **should yield a checkout pinned to the mirror's state, not to upstream's newer state, until the next `ensure`** — commit upstream *after* `ensure`, open `tree(ref_a)`, assert the pre-commit content; then `ensure` + `tree` again. Pins that freshness is `ensure`'s job, not `tree`'s.
11. **should check out a raw commit SHA, detached, not only a branch name** — `src/ingestion/writer.py` passes `push.after` and `src/knowledge/sync.py` does the same. Assert `rev-parse HEAD` equals the requested SHA and `symbolic-ref -q HEAD` fails.
12. **should place the worktree under `{mirror_root}/worktrees` and never inside the bare store** — assert `path.parent`, `path.name.startswith("wt-")`, and that nothing new appeared inside `{repo}.git` except worktree metadata.
13. **should keep the yielded path readable after the `with` block exits, until the repo's next `ensure`** — deliberately pins the deferred-reclamation contract that a future reader is most likely to "fix" into a `finally: worktree remove`.
14. **should still register the worktree for reclamation and re-raise when the caller's block raises** — then `ensure` and assert the path is gone; the exception path must not leak disk.
15. **should raise rather than yield an empty tree when the ref does not exist** — must raise `subprocess.CalledProcessError` from `git worktree add`. Non-obvious and worth pinning explicitly: the `mkdtemp` scratch dir is created *before* the failing `worktree add` and the failure happens before the `try/yield`, so it is **never registered** in `_finished_worktrees` — an empty directory is left under the worktrees root until a `sweep_worktrees`. Assert that current shape so the leak is a decision on record rather than an accident.
16. **should create the worktrees root on demand when it does not exist** — first `tree` call on a freshly `ensure`d mirror.

### `default_branch`

17. **should return the branch upstream's HEAD actually points at, not `main`/`master` and not the first branch alphabetically** — with the fixture as-is this is `local_upstream.ref_b` (`"feature"`). Assert `== ref_b` and, for teeth, `!= "main"` and `!= ref_a`. If the fixture is ever changed to end on `trunk`, this test must re-point HEAD itself with `git -C upstream symbolic-ref HEAD refs/heads/feature` — say so in a comment.
18. **should keep reporting the branch captured at clone time when upstream's HEAD moves afterwards** — a known limitation, not a bug being asserted as good: `git fetch --prune` does not update a mirror's local HEAD (that needs `git remote set-head`). Pin it so the behavior is explicit; this is the one test that changes if the team decides HEAD should follow upstream.
19. **should read the requested repo's HEAD and no other repo's** — needs a locally built `RepoMirror` whose `clone_source` maps two repo names to two upstreams with different HEADs.
20. **should raise rather than return an empty string when the repo was never ensured** — lower priority (loud failure), but included because the silent alternative — `""` flowing into `resolve_canonical_ref` and then into a checkout — is the exact hazard this area is about.

### `resolve_canonical_ref`

21. **should return the configured override without consulting the mirror when `canonical_refs` has an entry for the repo** — non-obvious setup: pass a mirror that has *not* been `ensure`d (so `default_branch` would raise) — reaching it is then a hard failure rather than a soft assertion.
22. **should fall back to the mirror's default branch when the repo has no override** — assert `== local_upstream.ref_b` with `canonical_refs={}`.
23. **should not apply another repo's override** — `canonical_refs={"other-repo": "trunk"}` for `REPO` must fall through to the default branch.
24. **should treat an empty-string override as an override, not as absent** — current code tests `override is not None`, so `""` is returned verbatim. Pin the behavior; if it is judged wrong, this test is where it gets decided.

### `sweep_worktrees`

25. **should remove every leftover worktree directory under `{mirror_root}/worktrees`** — Setup: `ensure`, open/exit two trees (still on disk by design), then build a **new** `RepoMirror` over the same `mirror_root` to model a restart with an empty in-memory list, and sweep.
26. **should be a no-op that does not raise when the worktrees root, or `mirror_root` itself, does not exist** — two variants; in the `mirror_root`-absent case also assert `mirror_root` is still absent afterwards.
27. **should leave every bare object store and its refs intact** — the "reaching too widely silently removes state" hazard: after sweeping, assert both refs still resolve and a fresh `tree(ref_a)` still yields `"content-a"`.
28. **should not touch anything outside `{mirror_root}/worktrees`** — plant decoys at `mirror_root/"keep.txt"`, `mirror_root/"other-state"/`, and `tmp_path/"outside"/`.
29. **should prune stale worktree metadata for every bare repo under the root** — after the sweep, `git worktree list --porcelain` in each bare has exactly one entry, and a subsequent `ensure` + `tree` cycle works normally.
30. **should destroy a worktree that is open at the moment it runs** — pins that this is a startup-only operation and documents why `src/main.py` calls it before any `ensure`; without this test, a future caller may schedule it periodically and silently delete live state.
31. **should skip a directory under the root that matches `*.git` but is not a git repo, without raising** — the `worktree prune` `CalledProcessError` is suppressed, so the sweep must complete and still clear the worktrees root.

Known gap to state in the test module rather than fix: `self._mirror_root.glob("*.git")` is non-recursive, which matches today's flat layout because `clone_source` builds `https://github.com/{login}/{repo}.git` from a bare repo name with no slash. Do not "fix" it into `rglob` without a repo-naming change.

### Credential handling — `_credential_for` / `_run_git`

32. **should never persist the token in the bare store's `origin` URL** — real run against `local_upstream`: assert `git -C <bare> config --get remote.origin.url` equals the plain upstream path exactly, and that the raw text of `<bare>/config` contains neither an `Authorization` header nor any `x-access-token` string.
33. **should pass the token only through the git process environment, never through argv, when the source is https** — Setup: a locally built `RepoMirror` with `clone_source` returning an https URL, `auth.token` monkeypatched to `"ghs_SECRET"`, and `src.github.mirror.subprocess.run` monkeypatched to a recorder. Assert no argv element contains the token, the URL carries no `user:pass@` userinfo, and `env` carries `GIT_CONFIG_COUNT="1"`, `GIT_CONFIG_KEY_0="http.extraHeader"`, and `GIT_CONFIG_VALUE_0` holding `base64("x-access-token:ghs_SECRET")`.
34. **should carry the credential on the fetch path as well as the clone path** — a token dropped only on fetch fails silently for public repos and only bites on private ones.
35. **should not mint a token at all when the source has no http(s) scheme** — replace `auth.token` with a callable that raises, then `ensure` against `local_upstream` — it must succeed. Then table-check `_credential_for` directly over a plain path, `file://`, `ssh://…`, `git@github.com:acme/x.git` → `None`; `http://…`, `https://…` → the token.
36. **should keep the token out of the exception raised when a credentialed git command fails** — Setup: https source pointing at `https://127.0.0.1:1/x.git` (connection refused immediately, no real network). Assert the token appears in neither `str(exc)`, `exc.cmd`, `exc.stdout`, nor `exc.stderr`.

### `object_store_path`

37. **should return the path `ensure` cloned into, usable for bare history reads** — assert it equals `mirror_root/f"{repo}.git"`, that it is bare, and that `git -C <path> log --oneline` works with no worktree (this is what `src/changelog/*` and `src/versioning/versioner.py` rely on).
38. **should be a pure computation that creates nothing when called before `ensure`** — assert the returned path does not exist and `mirror_root` was not created.

## Gotchas

- **Deferred reclamation is the contract, not a leak.** Never assert `not path.exists()` right after a `with mirror.tree(...)` block — assert presence there and absence after the repo's next `ensure`. A "cleanup on exit" assertion would be red against correct code and would push a future implementer into the exact `worktree remove`-in-`finally` that the source's docstring explains is wrong.
- **Two independent observables for disk state.** Directory listing of `{mirror_root}/worktrees` and `git worktree list --porcelain` inside the bare can disagree — metadata can outlive a deleted directory (that is what `worktree prune` is for) and vice versa. Every reclamation/sweep case should assert both.
- **Restart is modeled by a new instance.** `_finished_worktrees` is per-instance in memory; a second `RepoMirror` over the same `mirror_root` is the only faithful stand-in for a crash/restart, and it is what makes `sweep_worktrees`' reason for existing testable.
- **git version differences.** Assert on `subprocess.CalledProcessError` type and `returncode` only — never on git's stderr wording, which drifts between versions. The `mkdtemp`-then-`worktree add` pattern relies on git accepting an existing *empty* directory; if a case ever fails on an older git, that is the reason.
- **Ambient environment.** `_run_git` merges `os.environ`, so a developer with `GIT_CONFIG_COUNT` set in their shell would collide with the credential env; a test inspecting `env` must assert on the specific keys, not on dict equality. Any repo built inside a test must reuse conftest's helpers so committer identity and initial branch stay pinned.
- **The `auth` fixture cannot mint.** `private_key="test-key"` is not a PEM. Every https-path case must monkeypatch `auth.token` or `subprocess.run`; a test that reaches `jwt.encode` is mis-set-up, not failing.
- **SCOPE GUARD — deliberately not planned here.** No concurrency scenarios (threads, `ThreadPoolExecutor`, interleaved `ensure`/`tree`, prune-vs-create races, clone-branch double entry): the concurrency surface is owned by OPEN roadmap task **20.2.1** (`.ai-factory/specs/66-repo-mirror-concurrency-contract.md`). No async/`await` conversion tests either: that is **20.2.2** (`.ai-factory/specs/61-repo-mirror-async-boundary.md`). Every case above is single-threaded and synchronous — plain `with` blocks rather than manual `__enter__`/`__exit__`, no executors — so that when 20.2.2 makes these methods awaitable, the whole file converts mechanically to `await` without re-deciding any behavior.

## Seam in place

The seam this plan asked for is present:

```python
RepoMirror(mirror_root, auth, clone_source, run=subprocess.run)
```

`run` is keyword-with-default, and **both** execution sites route through it — `default_branch` and the shared `_run_git` helper — so there is one seam, not two.

**Case-status changes against what this plan assumed:**

- **Cases 33, 34 and 36** (token in the environment and not in argv; the credential carried on fetch as well as clone; the token absent from the raised failure) are authored by constructing the mirror with a recording callable and asserting on what it received. No `monkeypatch.setattr` on the module, and no risk of the patch leaking into a neighbouring test.
- **Case 32** (the token never persisted into the bare store's `origin`) stays a real run against `local_upstream` — it asserts on written config, not on an invocation.
- Every other case keeps the default runner and the existing `mirror` / `local_upstream` / `auth` fixtures unchanged.

The recording callable must return a `subprocess.CompletedProcess`, since `default_branch` reads `.stdout` off it. A recorder that returns `None` fails in a way that looks like a mirror bug rather than a fixture bug.

### Historical — the friction this replaced

`mirror_root`, `auth`, and `clone_source` were already constructor parameters, `resolve_canonical_ref` took `mirror` as an argument, and `tree`'s `mkdtemp` scratch location was already pinned by `mirror_root` — none of those cost a test anything. The one friction was the process-execution call site: `subprocess.run(["git", ...])` was hardcoded inside `_run_git` and again inside `default_branch`, with no parameter offering a runner.

That matters for exactly one group of cases — the https credential path (cases 33, 34, 36). Its argv and its `GIT_CONFIG_*` / `Authorization` env are observable *only* by interception, because `_run_git` returns nothing a caller can inspect and real git cannot be pointed at a filesystem upstream while also exercising the https branch. So those cases must `monkeypatch.setattr(src.github.mirror.subprocess, "run", recorder)` rather than pass a recorder in.

**The refactor and the post-refactor API:**

Add a `run` callable constructor parameter defaulting to `subprocess.run`, and route `default_branch`'s direct call through it too so there is a single execution seam rather than two:

```python
RepoMirror(mirror_root, auth, clone_source, run=subprocess.run)
```

Cases 33, 34 and 36 then construct the mirror with a recording callable and assert on the recorded `(argv, env)` directly — no module patching, and no risk of the patch leaking into a neighbouring test. Every other case in this plan is unaffected and keeps using the real `subprocess.run` default.

Guard: `run` is keyword-with-default, so every existing call site — `src/main.py`, the four `scripts/*` entrypoints, and `tests/github/conftest.py`'s `mirror` fixture — is unchanged. This is a parameter addition only; worktree isolation, credential handling, and deferred reclamation timing all stay exactly as they are. Note this refactor touches the same `_run_git` body that 20.2.2 (`.ai-factory/specs/61-repo-mirror-async-boundary.md`) will move onto a thread — sequence the two deliberately rather than letting them collide.
