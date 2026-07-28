"""Drives `Versioner.next` over a real throwaway git repo through a
lightweight fake mirror, per the spec's verification list —
`.ai-factory/specs/19-versioning.md`. Back-merge detection is a mandated
red-test surface: a wrong check silently manufactures a spurious `-rc` or
skips a real release.
"""

import subprocess
from pathlib import Path

import pytest

from src.commits.collector import GitCommitCollector
from src.routing.models import BranchRole
from src.versioning.versioner import Version, Versioner

_TRUNK = "main"


def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _commit(message: str, cwd: Path) -> str:
    _git(
        "-c", "user.name=herald-test",
        "-c", "user.email=herald@test.invalid",
        "commit", "-q", "--allow-empty", "-m", message,
        cwd=cwd,
    )
    return _git("rev-parse", "HEAD", cwd=cwd).stdout.strip()


def _checkout_new_branch(repo: Path, branch: str, start_point: str) -> None:
    _git("checkout", "-q", "-b", branch, start_point, cwd=repo)


def _checkout(repo: Path, branch: str) -> None:
    _git("checkout", "-q", branch, cwd=repo)


def _merge(repo: Path, branch: str, message: str, no_ff: bool) -> str:
    args = ["merge", "-q", "--no-ff" if no_ff else "--ff-only", "-m", message, branch]
    _git(
        "-c", "user.name=herald-test",
        "-c", "user.email=herald@test.invalid",
        *args,
        cwd=repo,
    )
    return _git("rev-parse", "HEAD", cwd=repo).stdout.strip()


def _tag(repo: Path, name: str, ref: str) -> None:
    _git("tag", name, ref, cwd=repo)


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """A throwaway local git repo, pinned committer identity and branch name
    so the fixture is reproducible without relying on ambient git config."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git("init", "-q", "-b", _TRUNK, cwd=repo)
    return repo


class FakeMirror:
    """Exposes exactly what `Versioner` calls on the mirror:
    `object_store_path` (the fixture repo path — real bare/worktree
    separation isn't needed for these tests, `Versioner` only ever reads by
    SHA/tag) and `default_branch`."""

    def __init__(self, repo_path: Path, default_branch: str = _TRUNK) -> None:
        self._repo_path = repo_path
        self._default_branch = default_branch

    def object_store_path(self, repo: str) -> Path:
        return self._repo_path

    def default_branch(self, repo: str) -> str:
        return self._default_branch


@pytest.fixture
def collector() -> GitCommitCollector:
    return GitCommitCollector()


def _versioner(git_repo: Path, collector: GitCommitCollector, version_increment: str = "patch") -> Versioner:
    return Versioner(FakeMirror(git_repo), collector, version_increment)


def test_no_tags_first_staging_push_is_v0_1_0_rc(git_repo, collector):
    base_sha = _commit("base", cwd=git_repo)
    _checkout_new_branch(git_repo, "staging", base_sha)
    staging_sha = _commit("staging work", cwd=git_repo)
    versioner = _versioner(git_repo, collector)

    result = versioner.next("org/repo", BranchRole.STAGING, base_sha, staging_sha)

    assert result == Version(0, 1, 0, prerelease=True)


def test_no_tags_default_branch_push_with_no_candidate_is_v0_1_0(git_repo, collector):
    base_sha = _commit("base", cwd=git_repo)
    versioner = _versioner(git_repo, collector)

    result = versioner.next("org/repo", BranchRole.RELEASE, base_sha, base_sha)

    assert result == Version(0, 1, 0)


def test_two_successive_staging_pushes_each_advance_off_the_semver_max(git_repo, collector):
    base_sha = _commit("base", cwd=git_repo)
    _tag(git_repo, "v1.2.0", base_sha)
    _checkout_new_branch(git_repo, "staging", base_sha)
    first_sha = _commit("staging work 1", cwd=git_repo)
    versioner = _versioner(git_repo, collector)

    first = versioner.next("org/repo", BranchRole.STAGING, base_sha, first_sha)
    assert first == Version(1, 2, 1, prerelease=True)

    # Simulates the delivery pipeline (11.3) tagging the computed `-rc`
    # version onto the pushed commit before the next staging push arrives.
    _tag(git_repo, str(first), first_sha)
    second_sha = _commit("staging work 2", cwd=git_repo)

    second = versioner.next("org/repo", BranchRole.STAGING, first_sha, second_sha)

    assert second == Version(1, 2, 2, prerelease=True)


def test_promotion_adopts_reachable_rc_candidate_base_with_no_further_bump(git_repo, collector):
    base_sha = _commit("base", cwd=git_repo)
    _checkout_new_branch(git_repo, "staging", base_sha)
    staging_sha = _commit("staging work", cwd=git_repo)
    _tag(git_repo, "v1.3.0-rc", staging_sha)
    _checkout(git_repo, _TRUNK)
    after_sha = _merge(git_repo, "staging", "promote staging to main", no_ff=True)
    versioner = _versioner(git_repo, collector)

    result = versioner.next("org/repo", BranchRole.RELEASE, base_sha, after_sha)

    assert result == Version(1, 3, 0)


def test_hotfix_bumps_off_last_full_release_when_no_reachable_candidate(git_repo, collector):
    base_sha = _commit("base", cwd=git_repo)
    _tag(git_repo, "v1.2.0", base_sha)
    hotfix_sha = _commit("hotfix", cwd=git_repo)
    versioner = _versioner(git_repo, collector)

    result = versioner.next("org/repo", BranchRole.RELEASE, base_sha, hotfix_sha)

    assert result == Version(1, 2, 1)


def test_fast_forward_back_merge_into_staging_returns_none(git_repo, collector):
    base_sha = _commit("base", cwd=git_repo)
    _checkout_new_branch(git_repo, "staging", base_sha)
    _checkout(git_repo, _TRUNK)
    _commit("main progress", cwd=git_repo)
    _checkout(git_repo, "staging")
    after_sha = _merge(git_repo, _TRUNK, "ff merge main into staging", no_ff=False)
    versioner = _versioner(git_repo, collector)

    result = versioner.next("org/repo", BranchRole.STAGING, base_sha, after_sha)

    assert result is None


def test_merge_commit_back_merge_round_trip_of_a_released_hotfix_returns_none(git_repo, collector):
    # The mandated red case: a hotfix commit lands on the default branch and
    # is released (a full tag points at it), then is back-merged into
    # staging via a real merge commit with no staging-unique non-merge work.
    base_sha = _commit("base", cwd=git_repo)
    _checkout_new_branch(git_repo, "staging", base_sha)
    _checkout(git_repo, _TRUNK)
    hotfix_sha = _commit("hotfix", cwd=git_repo)
    _tag(git_repo, "v1.2.1", hotfix_sha)
    _checkout(git_repo, "staging")
    merge_sha = _merge(git_repo, _TRUNK, "merge main into staging", no_ff=True)
    versioner = _versioner(git_repo, collector)

    result = versioner.next("org/repo", BranchRole.STAGING, base_sha, merge_sha)

    assert result is None


def test_semver_aware_selection_prefers_v1_10_0_over_v1_9_0(git_repo, collector):
    base_sha = _commit("base", cwd=git_repo)
    _tag(git_repo, "v1.9.0", base_sha)
    _tag(git_repo, "v1.10.0", base_sha)
    _checkout_new_branch(git_repo, "staging", base_sha)
    staging_sha = _commit("staging work", cwd=git_repo)
    versioner = _versioner(git_repo, collector)

    result = versioner.next("org/repo", BranchRole.STAGING, base_sha, staging_sha)

    assert result == Version(1, 10, 1, prerelease=True)
