"""Single-threaded tests pinning `RepoMirror`'s lifecycle, ref resolution, and
on-disk worktree state: `ensure`'s clone-vs-fetch and prune, `tree`'s pinned
content and deferred reclamation, `default_branch`, `resolve_canonical_ref`,
`sweep_worktrees`, and `object_store_path`.

Concurrency (threads, interleaved calls) is covered separately in
`test_mirror_isolation.py` and stays out of this module; so does credential
handling (`_credential_for` / `_run_git`'s env-based token passing), which is
its own module. Every case here drives the awaitable API directly —
`await mirror.ensure(...)`/`await mirror.default_branch(...)` and
`async with mirror.tree(...)` — using plain `async with` blocks rather than
manual `__aenter__`/`__aexit__` where possible.

Deferred reclamation is the contract, not a leak: a worktree yielded by
`tree()` stays valid on disk after its `with` block exits, until the repo's
next `ensure()` call. No case here asserts a path is gone right after its
`with` block — that would be red against correct code.
"""

import shutil
import subprocess

import pytest

from src.github.app_auth import GitHubAppAuth
from src.github.mirror import RepoMirror, resolve_canonical_ref
from tests.github.conftest import _commit, _git

REPO = "example-repo"
ORG_ID = 1


# --- Phase 1: `ensure` — clone, fetch, prune, worktree reclamation ---------


async def test_ensure_creates_bare_object_store_on_first_clone(mirror, tmp_path):
    bare_path = tmp_path / "mirror" / f"{REPO}.git"
    assert not bare_path.exists()

    await mirror.ensure(REPO, ORG_ID)

    assert bare_path.exists()
    result = subprocess.run(
        ["git", "rev-parse", "--is-bare-repository"],
        cwd=bare_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "true"


async def test_ensure_fetches_into_existing_store_rather_than_recloning(mirror, local_upstream):
    await mirror.ensure(REPO, ORG_ID)
    bare_path = mirror.object_store_path(REPO)
    sentinel = bare_path / "herald-sentinel.txt"
    sentinel.write_text("still here")

    _git("checkout", "-q", "-b", "new-branch", cwd=local_upstream.path)
    (local_upstream.path / "marker.txt").write_text("content-new")
    _git("add", "marker.txt", cwd=local_upstream.path)
    _commit("commit on new branch", cwd=local_upstream.path)

    await mirror.ensure(REPO, ORG_ID)

    # Both halves matter: a re-clone would also pick up the new ref, so the
    # sentinel's survival is what actually distinguishes fetch from re-clone.
    assert sentinel.exists()
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "refs/heads/new-branch"],
        cwd=bare_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0


async def test_ensure_adopts_rewritten_history_after_upstream_force_push(mirror, local_upstream):
    await mirror.ensure(REPO, ORG_ID)
    bare_path = mirror.object_store_path(REPO)

    # Build the rewritten history on a scratch branch off `ref_a`'s tip,
    # without ever checking `ref_a` itself out, then force `ref_a` onto it —
    # `git branch -f`, mirroring a force-push upstream did not need to touch
    # its own checked-out branch (`feature`, per the fixture) to perform.
    _git("checkout", "-q", "-b", "scratch", local_upstream.ref_a, cwd=local_upstream.path)
    (local_upstream.path / "marker.txt").write_text("content-a-rewritten")
    _git("add", "marker.txt", cwd=local_upstream.path)
    _commit("rewritten trunk history", cwd=local_upstream.path)
    new_sha = subprocess.run(
        ["git", "rev-parse", "scratch"],
        cwd=local_upstream.path,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    _git("checkout", "-q", local_upstream.ref_b, cwd=local_upstream.path)
    _git("branch", "-f", local_upstream.ref_a, new_sha, cwd=local_upstream.path)
    _git("branch", "-D", "scratch", cwd=local_upstream.path)

    await mirror.ensure(REPO, ORG_ID)

    resolved = subprocess.run(
        ["git", "rev-parse", f"refs/heads/{local_upstream.ref_a}"],
        cwd=bare_path,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert resolved == new_sha


async def test_ensure_drops_ref_deleted_upstream(mirror, local_upstream):
    await mirror.ensure(REPO, ORG_ID)
    bare_path = mirror.object_store_path(REPO)

    # Upstream's HEAD already sits on `ref_b` (the fixture ends there), so
    # deleting `ref_a` needs no checkout.
    _git("branch", "-D", local_upstream.ref_a, cwd=local_upstream.path)

    await mirror.ensure(REPO, ORG_ID)

    result = subprocess.run(
        ["git", "rev-parse", "--verify", f"refs/heads/{local_upstream.ref_a}"],
        cwd=bare_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0


async def test_ensure_creates_mirror_root_including_missing_parents(tmp_path, local_upstream, auth):
    mirror_root = tmp_path / "a" / "b" / "mirror"
    local_mirror = RepoMirror(
        mirror_root=mirror_root,
        auth=auth,
        clone_source=lambda repo, org_id: str(local_upstream.path),
    )
    assert not mirror_root.exists()

    await local_mirror.ensure(REPO, ORG_ID)

    assert mirror_root.exists()
    assert (mirror_root / f"{REPO}.git").exists()


async def test_ensure_reclaims_finished_worktrees_and_leaves_open_one(mirror, local_upstream):
    await mirror.ensure(REPO, ORG_ID)
    bare_path = mirror.object_store_path(REPO)

    async with mirror.tree(REPO, ORG_ID, local_upstream.ref_a) as path_a:
        pass

    tree_b = mirror.tree(REPO, ORG_ID, local_upstream.ref_b)
    path_b = await tree_b.__aenter__()

    await mirror.ensure(REPO, ORG_ID)

    assert not path_a.exists()
    porcelain = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        cwd=bare_path,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert str(path_a) not in porcelain
    assert str(path_b) in porcelain
    assert path_b.exists()
    assert (path_b / "marker.txt").read_text() == "content-b"

    await tree_b.__aexit__(None, None, None)


async def test_ensure_does_not_reclaim_another_repos_finished_worktrees(mirror, local_upstream):
    other_repo = "other-repo"
    await mirror.ensure(REPO, ORG_ID)
    await mirror.ensure(other_repo, ORG_ID)

    async with mirror.tree(other_repo, ORG_ID, local_upstream.ref_a) as other_path:
        pass

    await mirror.ensure(REPO, ORG_ID)

    assert other_path.exists()
    other_bare = mirror.object_store_path(other_repo)
    porcelain = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        cwd=other_bare,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert str(other_path) in porcelain


async def test_ensure_does_not_raise_when_finished_worktree_dir_already_deleted(mirror, local_upstream):
    await mirror.ensure(REPO, ORG_ID)

    async with mirror.tree(REPO, ORG_ID, local_upstream.ref_a) as path_a:
        pass

    shutil.rmtree(path_a)

    await mirror.ensure(REPO, ORG_ID)  # must not raise


# --- Phase 2: `tree` — pinned content, detached checkout, deferred cleanup -


async def test_tree_yields_exact_ref_content_sequentially(mirror, local_upstream):
    await mirror.ensure(REPO, ORG_ID)

    async with mirror.tree(REPO, ORG_ID, local_upstream.ref_a) as path_a:
        content_a = (path_a / "marker.txt").read_text()

    async with mirror.tree(REPO, ORG_ID, local_upstream.ref_b) as path_b:
        content_b = (path_b / "marker.txt").read_text()

    assert content_a == "content-a"
    assert content_b == "content-b"
    assert content_a != content_b


async def test_tree_is_pinned_to_mirror_state_not_upstream_until_next_ensure(mirror, local_upstream):
    await mirror.ensure(REPO, ORG_ID)

    _git("checkout", "-q", local_upstream.ref_a, cwd=local_upstream.path)
    (local_upstream.path / "marker.txt").write_text("content-a-updated")
    _git("add", "marker.txt", cwd=local_upstream.path)
    _commit("update after ensure", cwd=local_upstream.path)
    _git("checkout", "-q", local_upstream.ref_b, cwd=local_upstream.path)

    async with mirror.tree(REPO, ORG_ID, local_upstream.ref_a) as path:
        assert (path / "marker.txt").read_text() == "content-a"

    await mirror.ensure(REPO, ORG_ID)

    async with mirror.tree(REPO, ORG_ID, local_upstream.ref_a) as path:
        assert (path / "marker.txt").read_text() == "content-a-updated"


async def test_tree_checks_out_raw_sha_detached(mirror, local_upstream):
    await mirror.ensure(REPO, ORG_ID)
    sha = subprocess.run(
        ["git", "rev-parse", local_upstream.ref_a],
        cwd=local_upstream.path,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    async with mirror.tree(REPO, ORG_ID, sha) as path:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=path,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        assert head == sha

        symbolic = subprocess.run(
            ["git", "symbolic-ref", "-q", "HEAD"],
            cwd=path,
            capture_output=True,
            text=True,
        )
        assert symbolic.returncode != 0


async def test_tree_places_worktree_under_worktrees_root_never_inside_bare(mirror, local_upstream):
    await mirror.ensure(REPO, ORG_ID)
    bare_path = mirror.object_store_path(REPO)
    worktrees_root = bare_path.parent / "worktrees"
    before = set(bare_path.iterdir())

    async with mirror.tree(REPO, ORG_ID, local_upstream.ref_a) as path:
        assert path.parent == worktrees_root
        assert path.name.startswith("wt-")

        after = set(bare_path.iterdir())
        new_entries = after - before
        # The only thing `git worktree add` is allowed to create inside the
        # bare store itself is its own internal worktree metadata directory.
        assert all(entry.name == "worktrees" for entry in new_entries)


async def test_tree_creates_worktrees_root_on_demand(mirror, local_upstream):
    await mirror.ensure(REPO, ORG_ID)
    worktrees_root = mirror.object_store_path(REPO).parent / "worktrees"
    assert not worktrees_root.exists()

    async with mirror.tree(REPO, ORG_ID, local_upstream.ref_a):
        assert worktrees_root.exists()


async def test_tree_path_stays_readable_after_exit_until_next_ensure(mirror, local_upstream):
    await mirror.ensure(REPO, ORG_ID)

    async with mirror.tree(REPO, ORG_ID, local_upstream.ref_a) as path:
        pass

    # Deliberately not wrapped in `not path.exists()` right after the block:
    # this is the deferred-reclamation contract, asserted as presence.
    assert path.exists()
    assert (path / "marker.txt").read_text() == "content-a"


async def test_tree_registers_for_reclamation_and_reraises_on_error(mirror, local_upstream):
    await mirror.ensure(REPO, ORG_ID)
    bare_path = mirror.object_store_path(REPO)

    captured_path = None
    with pytest.raises(RuntimeError, match="boom"):
        async with mirror.tree(REPO, ORG_ID, local_upstream.ref_a) as path:
            captured_path = path
            raise RuntimeError("boom")

    assert captured_path is not None
    assert captured_path.exists()

    await mirror.ensure(REPO, ORG_ID)

    assert not captured_path.exists()
    porcelain = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        cwd=bare_path,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert str(captured_path) not in porcelain


async def test_tree_raises_on_missing_ref_and_leaks_empty_scratch_dir(mirror, local_upstream):
    await mirror.ensure(REPO, ORG_ID)
    worktrees_root = mirror.object_store_path(REPO).parent / "worktrees"

    with pytest.raises(subprocess.CalledProcessError):
        async with mirror.tree(REPO, ORG_ID, "does-not-exist"):
            pass

    # The `mkdtemp` scratch dir is created before the failing `worktree add`,
    # and the failure happens before `try`/`yield`, so it is never
    # registered in `_finished_worktrees` — it is left behind, empty, until a
    # `sweep_worktrees` call. Pinning this so the leak is a decision on
    # record, not an accident a future change silently fixes.
    leftover = list(worktrees_root.iterdir())
    assert len(leftover) == 1
    assert leftover[0].name.startswith("wt-")
    assert list(leftover[0].iterdir()) == []


# --- Phase 3: `default_branch` and `resolve_canonical_ref` ------------------


async def test_default_branch_returns_upstreams_actual_head(mirror, local_upstream):
    # `local_upstream` ends with `git checkout -b feature`, so upstream's
    # HEAD already points at `refs/heads/feature` (`ref_b`) — the "default
    # branch is not main/master" condition, for free. If the fixture is ever
    # changed to end on `trunk` instead, this test must re-point HEAD itself:
    #   git -C local_upstream.path symbolic-ref HEAD refs/heads/feature
    await mirror.ensure(REPO, ORG_ID)

    branch = await mirror.default_branch(REPO)

    assert branch == local_upstream.ref_b
    assert branch != "main"
    assert branch != local_upstream.ref_a


async def test_default_branch_tracks_upstream_head_across_ensure(mirror, local_upstream):
    await mirror.ensure(REPO, ORG_ID)
    assert await mirror.default_branch(REPO) == local_upstream.ref_b

    # Verified git behavior: `ensure` clones with `git clone --mirror`, which
    # sets `remote.origin.mirror=true`; a mirror remote's subsequent
    # `git fetch --prune origin` follows upstream's HEAD across the fetch,
    # unlike a plain (non-mirror) bare clone. This pins the *tracking*
    # contract, not drift-immunity — if the team later decides the canonical
    # ref must not move when upstream renames its default, that is a
    # source-behavior change to `RepoMirror`, not a test to encode here.
    _git("symbolic-ref", "HEAD", f"refs/heads/{local_upstream.ref_a}", cwd=local_upstream.path)
    await mirror.ensure(REPO, ORG_ID)

    assert await mirror.default_branch(REPO) == local_upstream.ref_a


async def test_default_branch_reads_only_the_requested_repos_head(tmp_path, auth):
    upstream_one = tmp_path / "upstream-one"
    upstream_one.mkdir()
    _git("init", "-q", "-b", "trunk", cwd=upstream_one)
    (upstream_one / "marker.txt").write_text("one")
    _git("add", "marker.txt", cwd=upstream_one)
    _commit("init one", cwd=upstream_one)

    upstream_two = tmp_path / "upstream-two"
    upstream_two.mkdir()
    _git("init", "-q", "-b", "main", cwd=upstream_two)
    (upstream_two / "marker.txt").write_text("two")
    _git("add", "marker.txt", cwd=upstream_two)
    _commit("init two", cwd=upstream_two)
    _git("checkout", "-q", "-b", "release", cwd=upstream_two)

    sources = {"repo-one": upstream_one, "repo-two": upstream_two}
    local_mirror = RepoMirror(
        mirror_root=tmp_path / "mirror",
        auth=auth,
        clone_source=lambda repo, org_id: str(sources[repo]),
    )
    await local_mirror.ensure("repo-one", ORG_ID)
    await local_mirror.ensure("repo-two", ORG_ID)

    assert await local_mirror.default_branch("repo-one") == "trunk"
    assert await local_mirror.default_branch("repo-two") == "release"


async def test_default_branch_raises_when_repo_never_ensured(mirror):
    # The bare path does not exist, so `self._run([...], cwd=<missing dir>)`
    # fails at process spawn (cannot chdir into it) — `FileNotFoundError`,
    # not `subprocess.CalledProcessError`. Verified against the real call.
    with pytest.raises(FileNotFoundError):
        await mirror.default_branch(REPO)


async def test_resolve_canonical_ref_returns_override_without_consulting_mirror(mirror):
    # `mirror` here is deliberately never `ensure`d — if `resolve_canonical_ref`
    # reached `default_branch`, this would fail loudly rather than pass softly.
    result = await resolve_canonical_ref(REPO, {REPO: "release"}, mirror)
    assert result == "release"


async def test_resolve_canonical_ref_falls_back_to_default_branch(mirror, local_upstream):
    await mirror.ensure(REPO, ORG_ID)
    result = await resolve_canonical_ref(REPO, {}, mirror)
    assert result == local_upstream.ref_b


async def test_resolve_canonical_ref_does_not_apply_another_repos_override(mirror, local_upstream):
    await mirror.ensure(REPO, ORG_ID)
    result = await resolve_canonical_ref(REPO, {"other-repo": "trunk"}, mirror)
    assert result == local_upstream.ref_b


async def test_resolve_canonical_ref_treats_empty_string_override_as_present(mirror):
    # Current code tests `override is not None`, so `""` is returned
    # verbatim rather than falling through to the mirror's default branch.
    result = await resolve_canonical_ref(REPO, {REPO: ""}, mirror)
    assert result == ""


# --- Phase 4: `sweep_worktrees` — startup reclamation -----------------------
#
# Known non-recursive-glob gap, left as-is: `sweep_worktrees` scans
# `self._mirror_root.glob("*.git")`, not `rglob`. That matches today's flat
# layout because `clone_source` builds URLs from a slash-free bare repo name
# (`{repo}.git` directly under `mirror_root`). Do not "fix" this into `rglob`
# without a repo-naming change that would actually produce nested `*.git`
# directories.


async def test_sweep_worktrees_removes_every_leftover_worktree(mirror, local_upstream, auth):
    await mirror.ensure(REPO, ORG_ID)
    async with mirror.tree(REPO, ORG_ID, local_upstream.ref_a):
        pass
    async with mirror.tree(REPO, ORG_ID, local_upstream.ref_b):
        pass

    bare_path = mirror.object_store_path(REPO)
    mirror_root = bare_path.parent
    worktrees_root = mirror_root / "worktrees"
    assert len(list(worktrees_root.iterdir())) == 2

    # Restart is modeled by a new instance over the same mirror_root: the
    # deferred-reclamation list is per-instance in memory.
    restarted = RepoMirror(
        mirror_root=mirror_root,
        auth=auth,
        clone_source=lambda repo, org_id: str(local_upstream.path),
    )
    await restarted.sweep_worktrees()

    assert list(worktrees_root.iterdir()) == []
    porcelain = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        cwd=bare_path,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    # A bare repo always reports its own baseline entry; one "worktree "
    # occurrence means every linked worktree's metadata is gone too.
    assert porcelain.count("worktree ") == 1


async def test_sweep_worktrees_is_noop_when_worktrees_root_missing(mirror):
    await mirror.ensure(REPO, ORG_ID)

    await mirror.sweep_worktrees()  # must not raise


async def test_sweep_worktrees_is_noop_when_mirror_root_missing(tmp_path, auth, local_upstream):
    mirror_root = tmp_path / "never-created"
    local_mirror = RepoMirror(
        mirror_root=mirror_root,
        auth=auth,
        clone_source=lambda repo, org_id: str(local_upstream.path),
    )

    await local_mirror.sweep_worktrees()  # must not raise

    assert not mirror_root.exists()


async def test_sweep_worktrees_leaves_bare_stores_and_refs_intact(mirror, local_upstream):
    await mirror.ensure(REPO, ORG_ID)
    async with mirror.tree(REPO, ORG_ID, local_upstream.ref_a):
        pass

    await mirror.sweep_worktrees()

    bare_path = mirror.object_store_path(REPO)
    for ref in (local_upstream.ref_a, local_upstream.ref_b):
        subprocess.run(
            ["git", "rev-parse", "--verify", f"refs/heads/{ref}"],
            cwd=bare_path,
            capture_output=True,
            text=True,
            check=True,
        )

    async with mirror.tree(REPO, ORG_ID, local_upstream.ref_a) as path:
        assert (path / "marker.txt").read_text() == "content-a"


async def test_sweep_worktrees_does_not_touch_anything_outside_worktrees_root(mirror, tmp_path):
    await mirror.ensure(REPO, ORG_ID)
    mirror_root = mirror.object_store_path(REPO).parent

    keep_file = mirror_root / "keep.txt"
    keep_file.write_text("keep")
    other_state = mirror_root / "other-state"
    other_state.mkdir()
    (other_state / "data.txt").write_text("data")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "data.txt").write_text("data")

    await mirror.sweep_worktrees()

    assert keep_file.exists()
    assert (other_state / "data.txt").exists()
    assert (outside / "data.txt").exists()


async def test_sweep_worktrees_prunes_stale_metadata_for_every_bare_repo(mirror, local_upstream, auth):
    other_repo = "other-repo"
    await mirror.ensure(REPO, ORG_ID)
    await mirror.ensure(other_repo, ORG_ID)
    async with mirror.tree(REPO, ORG_ID, local_upstream.ref_a):
        pass
    async with mirror.tree(other_repo, ORG_ID, local_upstream.ref_a):
        pass

    mirror_root = mirror.object_store_path(REPO).parent
    restarted = RepoMirror(
        mirror_root=mirror_root,
        auth=auth,
        clone_source=lambda repo, org_id: str(local_upstream.path),
    )
    await restarted.sweep_worktrees()

    for repo in (REPO, other_repo):
        bare_path = mirror_root / f"{repo}.git"
        porcelain = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            cwd=bare_path,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        assert porcelain.count("worktree ") == 1

    await restarted.ensure(REPO, ORG_ID)
    async with restarted.tree(REPO, ORG_ID, local_upstream.ref_b) as path:
        assert (path / "marker.txt").read_text() == "content-b"


async def test_sweep_worktrees_destroys_a_worktree_that_is_open_when_it_runs(mirror, local_upstream, auth):
    # Pins that `sweep_worktrees` is a startup-only operation, run once
    # before any `ensure` — the reason `src/main.py` calls it there and
    # nowhere else. A caller that schedules it periodically against a live
    # mirror would delete a worktree another operation is actively using.
    await mirror.ensure(REPO, ORG_ID)
    tree_ctx = mirror.tree(REPO, ORG_ID, local_upstream.ref_a)
    path = await tree_ctx.__aenter__()
    assert path.exists()

    mirror_root = mirror.object_store_path(REPO).parent
    restarted = RepoMirror(
        mirror_root=mirror_root,
        auth=auth,
        clone_source=lambda repo, org_id: str(local_upstream.path),
    )
    await restarted.sweep_worktrees()

    assert not path.exists()

    await tree_ctx.__aexit__(None, None, None)


async def test_sweep_worktrees_skips_non_git_directory_matching_glob(mirror):
    await mirror.ensure(REPO, ORG_ID)
    mirror_root = mirror.object_store_path(REPO).parent
    fake_bare = mirror_root / "not-a-repo.git"
    fake_bare.mkdir()
    (fake_bare / "some-file.txt").write_text("not a git repo")

    await mirror.sweep_worktrees()  # must not raise despite `worktree prune` failing here

    worktrees_root = mirror_root / "worktrees"
    if worktrees_root.exists():
        assert list(worktrees_root.iterdir()) == []


# --- Phase 5: `object_store_path` -------------------------------------------


async def test_object_store_path_returns_the_bare_clone_path(mirror, tmp_path):
    await mirror.ensure(REPO, ORG_ID)
    path = mirror.object_store_path(REPO)

    assert path == tmp_path / "mirror" / f"{REPO}.git"

    result = subprocess.run(
        ["git", "rev-parse", "--is-bare-repository"],
        cwd=path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "true"

    subprocess.run(
        ["git", "log", "--oneline"],
        cwd=path,
        capture_output=True,
        text=True,
        check=True,
    )


def test_object_store_path_creates_nothing_before_ensure(mirror, tmp_path):
    path = mirror.object_store_path(REPO)

    assert not path.exists()
    assert not (tmp_path / "mirror").exists()
