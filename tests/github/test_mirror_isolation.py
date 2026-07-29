"""The concurrency contract for `RepoMirror`.

Two groups live here. The first two tests use plain `ThreadPoolExecutor`
workers against the real (synchronous) `mirror` fixture to pin the
torn-tree isolation contract: concurrent `tree()` calls for the same repo
never share a mutable checkout, and tearing one down never disturbs a
still-open sibling.

The remaining scenarios go further: each uses the `GatedRunner` from
`conftest.py` to force a genuine thread interleaving over real git
subprocesses at a specific point — the exact overlap a later conversion of
`RepoMirror`'s git calls to `async`/`await` needs to keep safe, once a
single lock held across a whole method no longer serializes coroutines the
way it serializes today's threads. Each such scenario's docstring records
whether the observed run is red against today's synchronous mirror (a real
concurrency bug, visible today only because nothing serializes it) or
inapplicable against it (the invariant already holds today, for a stated
reason) — and why — so the invariant that must survive the conversion is
pinned either way.
"""

import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor

from tests.github.conftest import GatedRunner, build_gated_mirror

REPO = "example-repo"
ORG_ID = 1


def _read_tree(mirror, repo, org_id, ref):
    with mirror.tree(repo, org_id, ref) as path:
        content = (path / "marker.txt").read_text()
        return path, content


def test_concurrent_trees_at_different_refs_stay_isolated(mirror, local_upstream):
    mirror.ensure(REPO, ORG_ID)

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_a = executor.submit(_read_tree, mirror, REPO, ORG_ID, local_upstream.ref_a)
        future_b = executor.submit(_read_tree, mirror, REPO, ORG_ID, local_upstream.ref_b)
        path_a, content_a = future_a.result()
        path_b, content_b = future_b.result()

    assert path_a != path_b
    assert path_a.exists()
    assert path_b.exists()
    assert content_a == "content-a"
    assert content_b == "content-b"
    assert content_a != content_b


def test_teardown_of_one_tree_does_not_disturb_a_still_open_sibling(mirror, local_upstream):
    mirror.ensure(REPO, ORG_ID)

    tree_a = mirror.tree(REPO, ORG_ID, local_upstream.ref_a)
    path_a = tree_a.__enter__()

    tree_b = mirror.tree(REPO, ORG_ID, local_upstream.ref_b)
    path_b = tree_b.__enter__()

    tree_a.__exit__(None, None, None)

    assert path_b.exists()
    assert (path_b / "marker.txt").read_text() == "content-b"

    tree_b.__exit__(None, None, None)


def test_two_overlapping_ensures_never_both_take_the_clone_branch(tmp_path, local_upstream, auth):
    """Pins that `ensure`'s check-then-clone is not safe under genuine
    thread concurrency: two threads racing to establish the same repo's bare
    clone can both see no clone yet and both dispatch `git clone --mirror`.

    Two threads call `ensure` for a repo with no bare clone yet, gated so
    both pass the "no clone yet" check (seeing it false) before either's
    clone actually runs -- a two-party barrier on the `clone` command
    forces exactly that: it releases only once both threads have reached
    it, which is only possible while nothing serializes the check against
    the branch it feeds. The losing thread's clone then fails against a
    now-non-empty destination; that failure is expected and swallowed by
    the worker, since the invariant lives in how many clones were
    dispatched, not in whether a worker raised.

    Observed status: RED against today's synchronous mirror under real
    threads -- both threads take the clone branch and a clone is dispatched
    twice, so the assertion that it is dispatched exactly once fails. This
    is expected and by construction: nothing today serializes the check
    against the clone-or-fetch branch it guards. The scenario is also
    red-only by the shape of its own forcing harness, not only its
    assertion: the two-party barrier that deterministically produces this
    overlap can release only once both threads reach the gated clone, which
    is only possible while the bug is present. Once the check-then-branch
    is made safe, just one thread ever reaches a gated clone -- the other
    takes the fetch branch instead and never arrives at the gate -- so this
    same two-party barrier would then block the cloning thread forever.
    Making the invariant hold requires relaxing this forcing harness itself,
    not only the assertion; what must survive is "a clone is dispatched at
    most once", not this particular gate.
    """
    runner = GatedRunner()
    mirror = build_gated_mirror(tmp_path / "mirror", local_upstream, auth, runner)
    barrier = threading.Barrier(2)
    runner.add_gate("clone", release=barrier)

    def _ensure_worker():
        try:
            mirror.ensure(REPO, ORG_ID)
        except subprocess.CalledProcessError:
            # Expected once both threads take the clone branch: the winner's
            # `git clone --mirror` populates the destination first, so the
            # loser's clone fails against a now-non-empty directory. The
            # invariant lives in how many clones the runner recorded, not in
            # whether a worker raised.
            pass

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_a = executor.submit(_ensure_worker)
        future_b = executor.submit(_ensure_worker)
        future_a.result()
        future_b.result()

    clone_dispatches = sum(1 for call in runner.calls if call[1] == "clone")
    assert clone_dispatches == 1


def test_finished_worktree_bookkeeping_stays_consistent_under_thread_concurrency(
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
    fetch), forcing the two threads to genuinely run side by side; which of
    the two Python-level critical sections actually wins the lock
    afterwards is then left non-deterministic, on purpose. Either
    arbitration order must leave every worktree either fully reclaimed
    (gone from disk and from the list) or still pending (still on disk and
    still tracked for the next `ensure`) -- never dropped from tracking
    without being removed, and never removed twice. Releasing the gate also
    lets the `ensure`'s later `worktree prune` run ungated, incidentally
    alongside the still in-flight `worktree add` -- the mid-run consistency
    check below would catch a torn state from that overlap too, though
    forcing it deterministically is this module's other prune-vs-add
    scenario's job, not this one's.

    Observed status: INAPPLICABLE against today's synchronous mirror --
    passes under real threads because the existing lock around the append
    and the snapshot-clear already serializes them, so genuine thread
    concurrency does not break this invariant today. The scenario pins it
    so an equivalent guarantee must survive once a single lock no longer
    serializes every overlapping call the way it does for threads today.
    """
    runner = GatedRunner()
    mirror = build_gated_mirror(tmp_path / "mirror", local_upstream, auth, runner)
    bare_path = mirror.object_store_path(REPO)

    mirror.ensure(REPO, ORG_ID)
    with mirror.tree(REPO, ORG_ID, local_upstream.ref_a) as primed_path:
        pass  # registers one finished worktree ahead of the concurrent run

    barrier = threading.Barrier(2)
    runner.add_gate("fetch", release=barrier)
    runner.add_gate("worktree", "add", release=barrier)

    def _open_and_close_tree():
        with mirror.tree(REPO, ORG_ID, local_upstream.ref_b) as path:
            return path

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_tree = executor.submit(_open_and_close_tree)
        future_ensure = executor.submit(mirror.ensure, REPO, ORG_ID)
        second_path = future_tree.result()
        future_ensure.result()  # must not raise: a corrupted list would surface here

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
    mirror.ensure(REPO, ORG_ID)

    porcelain = _porcelain()
    for path in (primed_path, second_path):
        assert not path.exists()
        assert str(path) not in porcelain


def test_worktree_prune_does_not_race_a_worktree_being_created(tmp_path, local_upstream, auth):
    """Pins that a second `ensure`'s worktree prune and a concurrent
    `tree`'s worktree add for the same repo do not corrupt the worktree
    being created.

    Primes the bare clone with a first `ensure`, then forces a second
    `ensure`'s `worktree prune` to run at the same moment as a `tree`'s
    `worktree add --detach`, via a two-party gate on both commands. The
    created worktree must survive intact: its directory exists, it is
    listed by `git worktree list --porcelain`, and it reads the exact
    pinned ref content.

    Observed status: INAPPLICABLE against today's synchronous mirror -- the
    forced overlap does not reap or corrupt the worktree; the created
    worktree survives with its exact pinned content. The dangerous window
    this scenario targets is internal to a single `worktree add` subprocess
    and cannot be forced open from outside; today's synchronous mirror also
    never overlaps one repo's prune with its own worktree creation in the
    first place. The scenario pins this survival as the invariant a later
    concurrent mirror must also keep, in case the async conversion ever
    lets the two calls genuinely interleave at a finer grain.
    """
    runner = GatedRunner()
    mirror = build_gated_mirror(tmp_path / "mirror", local_upstream, auth, runner)
    bare_path = mirror.object_store_path(REPO)
    mirror.ensure(REPO, ORG_ID)

    barrier = threading.Barrier(2)
    runner.add_gate("worktree", "add", release=barrier)
    runner.add_gate("worktree", "prune", release=barrier)

    held = {}

    def _open_tree():
        ctx = mirror.tree(REPO, ORG_ID, local_upstream.ref_a)
        held["path"] = ctx.__enter__()
        held["ctx"] = ctx

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_tree = executor.submit(_open_tree)
        future_ensure = executor.submit(mirror.ensure, REPO, ORG_ID)
        future_tree.result()
        future_ensure.result()

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

    held["ctx"].__exit__(None, None, None)
    # The forced section is over: drop the gates before this solo `ensure`,
    # or its own `worktree prune` would re-trip the two-party prune gate and
    # block forever waiting for a second thread that is never coming.
    runner.clear_gates()
    mirror.ensure(REPO, ORG_ID)  # flush deferred reclamation, keep the mirror clean


def test_ensure_overlapping_an_open_tree_does_not_disturb_it(tmp_path, local_upstream, auth):
    """Extends the existing torn-tree isolation contract: an open `tree`
    must stay undisturbed while a concurrent `ensure` for the same repo runs
    its fetch, reclamation, and prune.

    Opens a `tree` and holds it, then runs `ensure` on another thread, using
    the gated runner to suspend that `ensure` mid-flight -- right before its
    fetch -- so the open tree can be read while `ensure` is genuinely
    in-progress, not only before or after it. The open tree's path and its
    exact pinned ref content must hold both while `ensure` is suspended
    there and after it completes.

    Observed status: INAPPLICABLE against today's synchronous mirror -- the
    open tree is undisturbed both during and after the overlapping
    `ensure`. `ensure` only reclaims worktrees already registered as
    finished (an open `tree` has not registered), `worktree prune` skips a
    live directory, and a detached checkout does not move when `fetch`
    updates branch refs -- so isolation holds structurally, and today the
    two calls also never actually overlap. The scenario pins this isolation
    across the overlap so it must keep holding once a later concurrent
    mirror can genuinely run `ensure` and `tree` for one repo at the same
    time.
    """
    runner = GatedRunner()
    mirror = build_gated_mirror(tmp_path / "mirror", local_upstream, auth, runner)
    bare_path = mirror.object_store_path(REPO)
    mirror.ensure(REPO, ORG_ID)

    tree_ctx = mirror.tree(REPO, ORG_ID, local_upstream.ref_a)
    path = tree_ctx.__enter__()

    release = threading.Event()
    reached = runner.add_gate("fetch", release=release)

    with ThreadPoolExecutor(max_workers=1) as executor:
        future_ensure = executor.submit(mirror.ensure, REPO, ORG_ID)
        assert reached.wait(timeout=5)

        # The overlapping `ensure` is now blocked mid-flight, right before
        # its `fetch` — the open tree must read exactly as pinned while
        # `ensure` is suspended there.
        assert path.exists()
        assert (path / "marker.txt").read_text() == "content-a"

        release.set()
        future_ensure.result()

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

    tree_ctx.__exit__(None, None, None)
    mirror.ensure(REPO, ORG_ID)
