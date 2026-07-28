# Test Plan: RepoMirror — lifecycle, refs and disk state

## Context
`RepoMirror` (`src/github/mirror.py`) keeps one bare object store per repo plus a fresh detached worktree per operation, and today only two concurrency tests touch it. This plan pins the non-concurrency, non-credential surfaces — `ensure`'s clone-vs-fetch and prune, `tree`'s deferred reclamation, `default_branch`, `resolve_canonical_ref`, `sweep_worktrees`, and `object_store_path` — where a wrong answer (indexing the wrong default branch, or a sweep removing live state) surfaces as bad output with no crash.

## Settings
- Testing: yes
- Logging: minimal
- Docs: no

## Test Command
`uv run pytest tests/github/test_mirror_lifecycle.py`

## Target Spec File
`tests/github/test_mirror_lifecycle.py`

## Fixtures & Conventions (read before writing)
- Reuse the three fixtures already in `tests/github/conftest.py` — `local_upstream`, `auth`, `mirror`. Do NOT invent new shared fixtures or edit conftest.
- Upstream `HEAD` points at `feature` (`local_upstream.ref_b`) because the fixture ends with `git checkout -b feature`; a `--mirror` clone copies that. This is the "default branch is not `main`" condition, for free.
- Module constants `REPO = "example-repo"` / `ORG_ID = 1`, matching `tests/github/test_mirror_isolation.py`.
- **Deferred reclamation is the contract.** Never assert `not path.exists()` right after a `with mirror.tree(...)` block exits — assert presence there, absence only after the repo's next `ensure`.
- **Assert disk and git separately.** Directory listing of `{mirror_root}/worktrees` and `git worktree list --porcelain` inside the bare can disagree; a reclamation/sweep case asserts both, and they are separate observables.
- **Restart is modeled by a new `RepoMirror` instance** over the same `mirror_root` — `_finished_worktrees` is per-instance in memory.
- When two *genuinely different* upstreams are needed, build a local `RepoMirror` inside that test rather than editing the shared fixture; reuse conftest's git helpers so committer identity and initial branch stay pinned.
- For a git command that runs but exits non-zero, assert on `subprocess.CalledProcessError` type and `returncode` only — never on git's stderr wording (it drifts between git versions). One case (Task 5, never-ensured `default_branch`) fails *before* git runs — a missing `cwd` — and raises `FileNotFoundError` instead; do not apply the `CalledProcessError` rule to it.
- **Out of scope (do not add):** the credential group (cases 32–36 of the spec — its own roadmap entry); any concurrency scenario (threads, executors, interleaved calls — roadmap 20.2.1); any async/`await` conversion (20.2.2). Every case here is single-threaded and synchronous with plain `with` blocks.

## Tasks

### Phase 1: `ensure` — clone, fetch, prune, worktree reclamation

- [x] **Task 1: `ensure` clone-vs-fetch and ref adoption**
  Files: `tests/github/test_mirror_lifecycle.py`
  Test cases:
  - `should create a bare object store at {mirror_root}/{repo}.git when the repo has never been cloned` (assert `mirror_root` absent beforehand, present after, and `git rev-parse --is-bare-repository` == `true`)
  - `should fetch into the existing store rather than re-cloning when the bare path already exists` (drop a sentinel file inside the bare dir after first `ensure`, add a new branch + commit upstream, `ensure` again; assert the sentinel survives AND the new upstream ref resolves — both halves)
  - `should adopt upstream's rewritten history when a ref was force-pushed` (`git branch -f trunk <new-sha>` upstream without checking it out, `ensure` again; assert `trunk` now resolves to the new SHA)
  - `should drop a ref that was deleted upstream` (delete an upstream branch, `ensure`, assert the ref no longer resolves in the bare — pins `--prune`)
  - `should create mirror_root including missing parents when it does not exist` (locally built `RepoMirror` pointed at `tmp_path/"a"/"b"/"mirror"`)

- [x] **Task 2: `ensure` deferred-worktree reclamation**
  Files: `tests/github/test_mirror_lifecycle.py`
  Test cases:
  - `should remove worktrees finished since the last call and leave a still-open one alone` (single-threaded: open+exit `tree(ref_a)`, open `tree(ref_b)` and keep open, `ensure`; assert path A gone from disk AND from `git worktree list --porcelain`, while path B still readable)
  - `should not reclaim another repo's finished worktrees when ensure runs for one repo` (pins reclamation keyed by bare path, not global)
  - `should not raise when a finished worktree's directory was already deleted out from under it` (`shutil.rmtree` the scratch dir after the `with` block, then `ensure`)

### Phase 2: `tree` — pinned content, detached checkout, deferred cleanup

- [x] **Task 3: `tree` content and pinning**
  Files: `tests/github/test_mirror_lifecycle.py`
  Test cases:
  - `should yield content that is exactly the requested ref's, sequentially for each ref` (single-threaded counterpart to the existing concurrency tests; `ref_a` -> `content-a`, `ref_b` -> `content-b`)
  - `should yield a checkout pinned to the mirror's state, not upstream's newer state, until the next ensure` (commit upstream AFTER `ensure`, open `tree(ref_a)`, assert pre-commit content; then `ensure` + `tree` again and assert the new content)
  - `should check out a raw commit SHA, detached, not only a branch name` (assert `git rev-parse HEAD` == requested SHA and `git symbolic-ref -q HEAD` fails)

- [x] **Task 4: `tree` worktree placement and lifecycle**
  Files: `tests/github/test_mirror_lifecycle.py`
  Test cases:
  - `should place the worktree under {mirror_root}/worktrees and never inside the bare store` (assert `path.parent` == worktrees root, `path.name.startswith("wt-")`, nothing new inside `{repo}.git` except worktree metadata)
  - `should create the worktrees root on demand when it does not exist` (first `tree` call on a freshly `ensure`d mirror)
  - `should keep the yielded path readable after the with block exits, until the repo's next ensure` (deliberately pins the deferred-reclamation contract — read content after `__exit__`, before `ensure`)
  - `should still register the worktree for reclamation and re-raise when the caller's block raises` (raise inside the `with`, assert it propagates, then `ensure` and assert the path is gone from disk and `git worktree list` — the exception path must not leak disk)
  - `should raise CalledProcessError rather than yield an empty tree when the ref does not exist` (must raise `subprocess.CalledProcessError` from `git worktree add`; also assert the never-registered empty `mkdtemp` scratch dir is left under the worktrees root until a `sweep_worktrees` — pin current shape so the leak is on record)

### Phase 3: `default_branch` and `resolve_canonical_ref`

- [x] **Task 5: `default_branch` HEAD resolution**
  Files: `tests/github/test_mirror_lifecycle.py`
  Test cases:
  - `should return the branch upstream's HEAD actually points at, not main/master and not the first branch alphabetically` (with the fixture as-is == `ref_b` == `"feature"`; also assert `!= "main"` and `!= ref_a`; comment that if the fixture ends on `trunk` this test must re-point HEAD with `git -C upstream symbolic-ref HEAD refs/heads/feature`)
  - `should track upstream's HEAD, refreshed on each ensure, when upstream's default branch moves` (move upstream HEAD to `ref_a` with `git -C upstream symbolic-ref HEAD refs/heads/trunk`, then re-`ensure` and assert `default_branch` == `ref_a`. **Verified git behavior** — the pin is the *tracking* contract, NOT drift-immunity: `ensure` clones with `git clone --mirror`, which sets `remote.origin.mirror=true`, so `git fetch --prune origin` follows upstream's HEAD across the fetch. Do NOT write this as "HEAD stays at the clone-time branch after a fetch" — that assertion is red against correct code. Spec case 18's "known limitation — `fetch` does not update a mirror's local HEAD" framing describes a *non-mirror* bare clone and misattributes it to `RepoMirror`; the spec is wrong on this point and should be corrected there too. If the team later decides the canonical ref must NOT drift when upstream renames its default, that is a `src/` source-behavior change — not a test to encode over today's code.)
  - `should read the requested repo's HEAD and no other repo's` (locally built `RepoMirror` whose `clone_source` maps two repo names to two upstreams with different HEADs)
  - `should raise rather than return an empty string when the repo was never ensured` (pins loud failure over `""` silently flowing into a checkout. **Not a `CalledProcessError`** — the bare path does not exist, so `self._run([...], cwd=<missing dir>)` fails at process spawn (cannot `chdir` into the missing directory) and raises **`FileNotFoundError`**, verified against the real call. Assert `pytest.raises(FileNotFoundError)`; the module's "assert `CalledProcessError` type/returncode only" convention applies to git-nonzero exits, NOT to this spawn-time failure.)

- [x] **Task 6: `resolve_canonical_ref` override policy**
  Files: `tests/github/test_mirror_lifecycle.py`
  Test cases:
  - `should return the configured override without consulting the mirror when canonical_refs has an entry for the repo` (pass a mirror NOT `ensure`d, so `default_branch` would raise — reaching it is a hard failure)
  - `should fall back to the mirror's default branch when the repo has no override` (assert `== ref_b` with `canonical_refs={}`)
  - `should not apply another repo's override` (`canonical_refs={"other-repo": "trunk"}` for `REPO` falls through to the default branch)
  - `should treat an empty-string override as an override, not as absent` (current code tests `override is not None`, so `""` is returned verbatim; pin the behavior)

### Phase 4: `sweep_worktrees` — startup reclamation

- [x] **Task 7: `sweep_worktrees` removal and preservation**
  Files: `tests/github/test_mirror_lifecycle.py`
  Test cases:
  - `should remove every leftover worktree directory under {mirror_root}/worktrees` (`ensure`, open/exit two trees so they stay on disk, build a NEW `RepoMirror` over the same `mirror_root` to model a restart with empty in-memory list, then sweep; assert disk and `git worktree list` both cleared)
  - `should be a no-op that does not raise when the worktrees root does not exist` (variant: worktrees root absent)
  - `should be a no-op that does not raise when mirror_root itself does not exist, and leave it absent` (variant: also assert `mirror_root` still absent afterwards)
  - `should leave every bare object store and its refs intact` (the "reaching too widely removes state" hazard: after sweeping, assert both refs still resolve AND a fresh `tree(ref_a)` still yields `"content-a"`)
  - `should not touch anything outside {mirror_root}/worktrees` (plant decoys at `mirror_root/"keep.txt"`, `mirror_root/"other-state"/`, and `tmp_path/"outside"/`; assert all survive)

- [x] **Task 8: `sweep_worktrees` metadata prune and edge cases**
  Files: `tests/github/test_mirror_lifecycle.py`
  Test cases:
  - `should prune stale worktree metadata for every bare repo under the root` (after sweep, `git worktree list --porcelain` in each bare has exactly one entry, and a subsequent `ensure` + `tree` cycle works normally)
  - `should destroy a worktree that is open at the moment it runs` (pins that this is a startup-only operation — documents why `src/main.py` calls it before any `ensure`; guards a future caller from scheduling it periodically and deleting live state)
  - `should skip a directory under the root that matches *.git but is not a git repo, without raising` (the `worktree prune` `CalledProcessError` is suppressed; sweep completes and still clears the worktrees root)
  - Add a module-level comment stating the known non-recursive-`glob("*.git")` gap: it matches today's flat layout because `clone_source` builds URLs from a slash-free bare repo name; do NOT "fix" it into `rglob` without a repo-naming change.

### Phase 5: `object_store_path`

- [x] **Task 9: `object_store_path` bare-history entry point**
  Files: `tests/github/test_mirror_lifecycle.py`
  Test cases:
  - `should return the path ensure cloned into, usable for bare history reads` (assert it equals `mirror_root/f"{repo}.git"`, is bare, and `git -C <path> log --oneline` works with no worktree)
  - `should be a pure computation that creates nothing when called before ensure` (assert the returned path does not exist and `mirror_root` was not created)
