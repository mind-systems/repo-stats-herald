"""Red concurrency tests pinning `RepoMirror`'s isolation and cleanup
invariants against the stub.

Both tests below fail because `ensure()`/`tree()` raise `NotImplementedError`
(the mirror/worktree logic is absent), never because of an import or fixture
error. The follow-up task's clone-or-fetch `ensure()` and worktree-per-
operation `tree()` turn them green unchanged.
"""

from concurrent.futures import ThreadPoolExecutor

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
