"""The concurrency contract for `RepoMirror`'s awaitable API.

Two groups live here. The first two tests drive concurrent coroutines
through `asyncio.gather` against the real `mirror` fixture to pin the
torn-tree isolation contract: concurrent `tree()` calls for the same repo
never share a mutable checkout, and tearing one down never disturbs a
still-open sibling.

The remaining scenarios go further: each uses the `GatedRunner` from
`conftest.py` to force a genuine interleaving over real git subprocesses at
a specific point — every shelling-out call runs on a thread `RepoMirror`
offloads to internally (`asyncio.to_thread`), so a gate set from inside one
coroutine's offloaded subprocess is still observed by another coroutine's
offloaded subprocess running concurrently on a different thread. `ensure`
serializes per repo behind a lock held across its whole body; `tree` takes
no such lock. Each scenario's docstring records whether the invariant it
pins is one `ensure`'s serialization must uphold, or one that already held
structurally (an open `tree` untouched by a concurrent `ensure`, or a
`tree`/`ensure` overlap git itself keeps safe) — and why.
"""

import asyncio
import subprocess
import threading

from tests.github.conftest import GatedRunner, build_gated_mirror

REPO = "example-repo"
ORG_ID = 1


async def _read_tree(mirror, repo, org_id, ref):
    async with mirror.tree(repo, org_id, ref) as path:
        content = (path / "marker.txt").read_text()
        return path, content


async def test_concurrent_trees_at_different_refs_stay_isolated(mirror, local_upstream):
    await mirror.ensure(REPO, ORG_ID)

    (path_a, content_a), (path_b, content_b) = await asyncio.gather(
        _read_tree(mirror, REPO, ORG_ID, local_upstream.ref_a),
        _read_tree(mirror, REPO, ORG_ID, local_upstream.ref_b),
    )

    assert path_a != path_b
    assert path_a.exists()
    assert path_b.exists()
    assert content_a == "content-a"
    assert content_b == "content-b"
    assert content_a != content_b


async def test_teardown_of_one_tree_does_not_disturb_a_still_open_sibling(mirror, local_upstream):
    await mirror.ensure(REPO, ORG_ID)

    tree_a = mirror.tree(REPO, ORG_ID, local_upstream.ref_a)
    path_a = await tree_a.__aenter__()

    tree_b = mirror.tree(REPO, ORG_ID, local_upstream.ref_b)
    path_b = await tree_b.__aenter__()

    await tree_a.__aexit__(None, None, None)

    assert path_b.exists()
    assert (path_b / "marker.txt").read_text() == "content-b"

    await tree_b.__aexit__(None, None, None)


async def test_two_overlapping_ensures_never_both_take_the_clone_branch(tmp_path, local_upstream, auth):
    """Pins that `ensure`'s per-repo serialization keeps a clone dispatched
    at most once, even when two coroutines race to establish the same
    repo's bare clone.

    Two `ensure` coroutines for a repo with no bare clone yet run
    concurrently via `asyncio.gather`. `ensure` holds a lazily-created
    per-repo `asyncio.Lock` across its whole body, so the second coroutine
    blocks on the lock until the first's clone/reclaim/prune sequence fully
    completes; by the time the second acquires the lock, the bare path
    already exists and it takes the fetch branch instead. No forcing
    harness is needed to observe this: unlike a two-party barrier gated on
    `clone` (which would require both coroutines to reach the clone branch
    simultaneously — a state the lock makes unreachable, and which would
    therefore hang forever), the outcome is deterministic once `ensure`
    serializes its own check-then-branch.
    """
    runner = GatedRunner()
    mirror = build_gated_mirror(tmp_path / "mirror", local_upstream, auth, runner)

    await asyncio.gather(
        mirror.ensure(REPO, ORG_ID),
        mirror.ensure(REPO, ORG_ID),
    )

    clone_dispatches = sum(1 for call in runner.calls if call[1] == "clone")
    assert clone_dispatches == 1


async def test_finished_worktree_bookkeeping_stays_consistent_under_thread_concurrency(
    tmp_path, local_upstream, auth
):
    """Pins that finished-worktree bookkeeping stays consistent when a
    `tree` teardown and an `ensure`'s reclamation genuinely overlap on real
    threads.

    Primes one already-finished worktree, then runs a second `tree`
    open/close concurrently with an `ensure` for the same repo -- the
    `tree`'s teardown appends to the finished-worktree list under a lock,
    and the `ensure`'s reclamation snapshots and clears that same list
    under the same lock. The gated runner only controls when the underlying
    git subprocesses run (the `tree`'s worktree-add and the `ensure`'s
    fetch), forcing the two coroutines' offloaded threads to genuinely run
    side by side; which of the two Python-level critical sections actually
    wins the lock afterwards is then left non-deterministic, on purpose.
    Either arbitration order must leave every worktree either fully
    reclaimed (gone from disk and from the list) or still pending (still on
    disk and still tracked for the next `ensure`) -- never dropped from
    tracking without being removed, and never removed twice. Releasing the
    gate also lets the `ensure`'s later `worktree prune` run ungated,
    incidentally alongside the still in-flight `worktree add` -- the
    mid-run consistency check below would catch a torn state from that
    overlap too, though forcing it deterministically is this module's other
    prune-vs-add scenario's job, not this one's.

    This invariant already held under real thread concurrency before
    `RepoMirror` grew an async boundary -- the lock around the append and
    the snapshot-clear serializes it regardless of whether the calling side
    is a thread or a coroutine whose subprocess is offloaded to one.
    """
    runner = GatedRunner()
    mirror = build_gated_mirror(tmp_path / "mirror", local_upstream, auth, runner)
    bare_path = mirror.object_store_path(REPO)

    await mirror.ensure(REPO, ORG_ID)
    async with mirror.tree(REPO, ORG_ID, local_upstream.ref_a) as primed_path:
        pass  # registers one finished worktree ahead of the concurrent run

    barrier = threading.Barrier(2)
    runner.add_gate("fetch", release=barrier)
    runner.add_gate("worktree", "add", release=barrier)

    async def _open_and_close_tree():
        async with mirror.tree(REPO, ORG_ID, local_upstream.ref_b) as path:
            return path

    second_path, _ = await asyncio.gather(
        _open_and_close_tree(),
        mirror.ensure(REPO, ORG_ID),  # must not raise: a corrupted list would surface here
    )

    def _porcelain() -> str:
        return subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            cwd=bare_path,
            capture_output=True,
            text=True,
            check=True,
        ).stdout

    for path in (primed_path, second_path):
        assert path.exists() == (str(path) in _porcelain())

    # Flush whichever side of the race lost the reclamation: a worktree
    # still pending after the concurrent run must be picked up by the next
    # `ensure`, exactly as if the race had never happened. The forced
    # section is over, so drop the gates first -- otherwise this solo
    # `ensure` would re-trip the two-party `fetch` gate and block forever
    # waiting for a second thread that is never coming.
    runner.clear_gates()
    await mirror.ensure(REPO, ORG_ID)

    porcelain = _porcelain()
    for path in (primed_path, second_path):
        assert not path.exists()
        assert str(path) not in porcelain


async def test_worktree_prune_does_not_race_a_worktree_being_created(tmp_path, local_upstream, auth):
    """Pins that a second `ensure`'s worktree prune and a concurrent
    `tree`'s worktree add for the same repo do not corrupt the worktree
    being created.

    Primes the bare clone with a first `ensure`, then forces a second
    `ensure`'s `worktree prune` to run at the same moment as a `tree`'s
    `worktree add --detach`, via a two-party gate on both commands. The
    created worktree must survive intact: its directory exists, it is
    listed by `git worktree list --porcelain`, and it reads the exact
    pinned ref content.

    This invariant already holds structurally -- the forced overlap does
    not reap or corrupt the worktree; the created worktree survives with
    its exact pinned content. The dangerous window this scenario targets is
    internal to a single `worktree add` subprocess and cannot be forced
    open from outside, and `tree` takes no per-repo lock, so a concurrent
    `ensure`'s prune genuinely can run alongside it -- git's own worktree
    handling keeps the pair safe regardless.
    """
    runner = GatedRunner()
    mirror = build_gated_mirror(tmp_path / "mirror", local_upstream, auth, runner)
    bare_path = mirror.object_store_path(REPO)
    await mirror.ensure(REPO, ORG_ID)

    barrier = threading.Barrier(2)
    runner.add_gate("worktree", "add", release=barrier)
    runner.add_gate("worktree", "prune", release=barrier)

    held = {}

    async def _open_tree():
        ctx = mirror.tree(REPO, ORG_ID, local_upstream.ref_a)
        held["path"] = await ctx.__aenter__()
        held["ctx"] = ctx

    await asyncio.gather(_open_tree(), mirror.ensure(REPO, ORG_ID))

    path = held["path"]
    assert path.exists()
    porcelain = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        cwd=bare_path,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert str(path) in porcelain
    assert (path / "marker.txt").read_text() == "content-a"

    await held["ctx"].__aexit__(None, None, None)
    # The forced section is over: drop the gates before this solo `ensure`,
    # or its own `worktree prune` would re-trip the two-party prune gate and
    # block forever waiting for a second thread that is never coming.
    runner.clear_gates()
    await mirror.ensure(REPO, ORG_ID)  # flush deferred reclamation, keep the mirror clean


async def test_ensure_overlapping_an_open_tree_does_not_disturb_it(tmp_path, local_upstream, auth):
    """Extends the existing torn-tree isolation contract: an open `tree`
    must stay undisturbed while a concurrent `ensure` for the same repo runs
    its fetch, reclamation, and prune.

    Opens a `tree` and holds it, then runs `ensure` as a second task, using
    the gated runner to suspend that `ensure` mid-flight -- right before its
    fetch -- so the open tree can be read while `ensure` is genuinely
    in-progress, not only before or after it. The open tree's path and its
    exact pinned ref content must hold both while `ensure` is suspended
    there and after it completes.

    This invariant already holds structurally -- the open tree is
    undisturbed both during and after the overlapping `ensure`. `ensure`
    only reclaims worktrees already registered as finished (an open `tree`
    has not registered), `worktree prune` skips a live directory, and a
    detached checkout does not move when `fetch` updates branch refs -- and
    `tree` takes no per-repo lock, so `ensure` and `tree` for one repo can
    genuinely run at the same time without disturbing each other.
    """
    runner = GatedRunner()
    mirror = build_gated_mirror(tmp_path / "mirror", local_upstream, auth, runner)
    bare_path = mirror.object_store_path(REPO)
    await mirror.ensure(REPO, ORG_ID)

    tree_ctx = mirror.tree(REPO, ORG_ID, local_upstream.ref_a)
    path = await tree_ctx.__aenter__()

    release = threading.Event()
    reached = runner.add_gate("fetch", release=release)

    ensure_task = asyncio.create_task(mirror.ensure(REPO, ORG_ID))
    assert await asyncio.to_thread(reached.wait, 5)

    # The overlapping `ensure` is now blocked mid-flight, right before
    # its `fetch` — the open tree must read exactly as pinned while
    # `ensure` is suspended there.
    assert path.exists()
    assert (path / "marker.txt").read_text() == "content-a"

    release.set()
    await ensure_task

    assert path.exists()
    porcelain = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        cwd=bare_path,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert str(path) in porcelain
    assert (path / "marker.txt").read_text() == "content-a"

    await tree_ctx.__aexit__(None, None, None)
    await mirror.ensure(REPO, ORG_ID)
