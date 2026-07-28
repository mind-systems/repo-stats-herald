import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.commits.collector import EMPTY_TREE_SHA, GitCommitCollector

_TRUNK = "main"


def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _checkout_new_branch(repo: Path, branch: str, start_point: str) -> None:
    _git("checkout", "-q", "-b", branch, start_point, cwd=repo)


def _checkout(repo: Path, branch: str) -> None:
    _git("checkout", "-q", branch, cwd=repo)


def _merge(repo: Path, branch: str, message: str, no_ff: bool) -> str:
    args = ["merge", "-q"]
    if no_ff:
        args += ["--no-ff"]
    else:
        args += ["--ff-only"]
    _git(
        "-c", "user.name=herald-test",
        "-c", "user.email=herald@test.invalid",
        *args, "-m", message, branch,
        cwd=repo,
    )
    return _git("rev-parse", "HEAD", cwd=repo).stdout.strip()


def _tag(repo: Path, name: str, ref: str) -> None:
    _git("tag", name, ref, cwd=repo)


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


def test_list_tags_returns_all_tag_names_parse_agnostic(git_repo, commit_at, collector):
    sha = commit_at(git_repo, "only")
    _tag(git_repo, "v1.0.0", sha)
    _tag(git_repo, "nightly", sha)

    tags = collector.list_tags(str(git_repo))

    assert set(tags) == {"v1.0.0", "nightly"}


def test_list_tags_returns_empty_tuple_when_repo_has_no_tags(git_repo, commit_at, collector):
    commit_at(git_repo, "only")

    assert collector.list_tags(str(git_repo)) == ()


def test_is_ancestor_true_when_sha_reachable_from_ref(git_repo, commit_at, collector):
    old_sha = commit_at(git_repo, "old")
    new_sha = commit_at(git_repo, "new")

    assert collector.is_ancestor(str(git_repo), old_sha, new_sha) is True


def test_is_ancestor_false_when_sha_not_reachable_from_ref(git_repo, commit_at, collector):
    base_sha = commit_at(git_repo, "base")
    _checkout_new_branch(git_repo, "side", base_sha)
    side_sha = commit_at(git_repo, "side commit")
    _checkout(git_repo, _TRUNK)
    trunk_sha = commit_at(git_repo, "trunk commit")

    assert collector.is_ancestor(str(git_repo), side_sha, trunk_sha) is False


def test_is_ancestor_false_for_unknown_ref_without_raising(git_repo, commit_at, collector):
    sha = commit_at(git_repo, "only")

    assert collector.is_ancestor(str(git_repo), sha, "does-not-exist") is False


def test_new_commits_empty_for_fast_forward_back_merge(git_repo, commit_at, collector):
    # `staging` forks off `base` with no commits of its own; `main` (the
    # default branch) then progresses, and `staging` fast-forwards onto it —
    # a back-merge with no staging-unique work.
    base_sha = commit_at(git_repo, "base")
    _checkout_new_branch(git_repo, "staging", base_sha)
    _checkout(git_repo, _TRUNK)
    commit_at(git_repo, "main progress")
    _checkout(git_repo, "staging")
    after_sha = _merge(git_repo, _TRUNK, "ff merge main into staging", no_ff=False)

    result = collector.new_commits(str(git_repo), base_sha, after_sha, _TRUNK)

    assert result == ()


def test_new_commits_empty_for_merge_commit_back_merge(git_repo, commit_at, collector):
    # `staging` forks off `base` with no commits of its own; `main` then
    # progresses with a hotfix, and `main` is merged into `staging` via a
    # real merge commit — the merge commit is dropped by `--no-merges` and
    # the hotfix itself is already reachable from `main`, so this reads as
    # empty just like the fast-forward case.
    base_sha = commit_at(git_repo, "base")
    _checkout_new_branch(git_repo, "staging", base_sha)
    _checkout(git_repo, _TRUNK)
    commit_at(git_repo, "hotfix")
    _checkout(git_repo, "staging")
    merge_sha = _merge(git_repo, _TRUNK, "merge main into staging", no_ff=True)

    result = collector.new_commits(str(git_repo), base_sha, merge_sha, _TRUNK)

    assert result == ()


def test_new_commits_returns_staging_unique_non_merge_commits(git_repo, commit_at, collector):
    base_sha = commit_at(git_repo, "base")
    _checkout_new_branch(git_repo, "staging", base_sha)
    staging_sha = commit_at(git_repo, "staging work")

    result = collector.new_commits(str(git_repo), base_sha, staging_sha, _TRUNK)

    assert result == (staging_sha,)


def test_collect_keeps_a_commit_whose_subject_contains_the_record_separator_byte(git_repo, commit_at, collector):
    commit_at(git_repo, "first commit")
    _git(
        "-c", "user.name=herald-test",
        "-c", "user.email=herald@test.invalid",
        "commit", "-q", "--allow-empty", "-m", "sub\x1eject",
        cwd=git_repo,
    )

    ctx = collector.collect(str(git_repo), "HEAD")

    assert len(ctx.commits) == 2
    assert "\x1e" in ctx.commits[0].message


def test_collect_keeps_a_commit_whose_body_contains_the_record_separator_byte(git_repo, commit_at, collector):
    commit_at(git_repo, "first commit")
    _git(
        "-c", "user.name=herald-test",
        "-c", "user.email=herald@test.invalid",
        "commit", "-q", "--allow-empty", "-m", "subject", "-m", "bo\x1edy",
        cwd=git_repo,
    )

    ctx = collector.collect(str(git_repo), "HEAD")

    assert len(ctx.commits) == 2
    assert "\x1e" in ctx.commits[0].message
