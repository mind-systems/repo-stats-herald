from datetime import datetime, timedelta, timezone

import pytest

from src.commits.collector import EMPTY_TREE_SHA, GitCommitCollector


@pytest.fixture
def collector() -> GitCommitCollector:
    return GitCommitCollector()


def test_commit_at_or_before_returns_newest_sha_at_or_before_timestamp(git_repo, commit_at, collector):
    now = datetime.now(timezone.utc)
    old_sha = commit_at(git_repo, "old", when=(now - timedelta(days=10)).isoformat())
    new_sha = commit_at(git_repo, "new", when=(now - timedelta(hours=1)).isoformat())

    assert collector.commit_at_or_before(str(git_repo), "main", now - timedelta(days=5)) == old_sha
    assert collector.commit_at_or_before(str(git_repo), "main", now) == new_sha


def test_commit_at_or_before_returns_none_when_no_commit_qualifies(git_repo, commit_at, collector):
    now = datetime.now(timezone.utc)
    commit_at(git_repo, "only", when=now.isoformat())

    result = collector.commit_at_or_before(str(git_repo), "main", now - timedelta(days=365))

    assert result is None


def test_active_branches_with_empty_tree_before_enumerates_without_raising(git_repo, commit_at, collector):
    sha = commit_at(git_repo, "only")

    branches = collector.active_branches(str(git_repo), EMPTY_TREE_SHA, sha)

    assert branches == [("main", EMPTY_TREE_SHA, sha)]


def test_active_branches_with_empty_tree_after_returns_empty_list_without_raising(git_repo, collector):
    # An empty repo (unborn HEAD, no commits at all): `after == EMPTY_TREE_SHA`
    # must short-circuit before either boundary's `commit_timestamp` runs,
    # which would otherwise raise on the tree-header (not a commit date)
    # `git show` prints for the empty-tree SHA.
    branches = collector.active_branches(str(git_repo), EMPTY_TREE_SHA, EMPTY_TREE_SHA)

    assert branches == []
