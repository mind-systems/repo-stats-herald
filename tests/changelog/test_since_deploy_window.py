"""Drives `SinceDeployWindow.resolve` over a real throwaway git repo through
a lightweight fake mirror, per the spec's guard-case list — the base tag
must be selected by `Version` ordering (never lexicographically, never by
commit date) and must come from the shared `GitCommitCollector.list_tags`
primitive rather than a private `git tag` call.
"""

import subprocess
from pathlib import Path

import pytest

from src.changelog.windows.since_deploy import SinceDeployWindow
from src.commits.collector import EMPTY_TREE_SHA, GitCommitCollector
from src.routing.models import BranchRole

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
    """Exposes exactly what `SinceDeployWindow` calls on the mirror:
    `object_store_path` (the fixture repo path — real bare/worktree
    separation isn't needed for these tests, `SinceDeployWindow` only ever
    reads tags by name)."""

    def __init__(self, repo_path: Path) -> None:
        self._repo_path = repo_path

    def object_store_path(self, repo: str) -> Path:
        return self._repo_path


class StubCollector:
    """A spy `GitCommitCollector` stand-in whose `list_tags` returns a fixed
    tuple and records whether it was called — pins that `SinceDeployWindow`
    reuses the injected collector rather than shelling its own `git tag`."""

    def __init__(self, tags: tuple[str, ...]) -> None:
        self._tags = tags
        self.list_tags_calls: list[str] = []

    def list_tags(self, repo_path: str) -> tuple[str, ...]:
        self.list_tags_calls.append(repo_path)
        return self._tags


@pytest.fixture
def collector() -> GitCommitCollector:
    return GitCommitCollector()


async def test_staging_after_full_release_is_not_the_rc(git_repo, collector):
    base_sha = _commit("base", cwd=git_repo)
    _tag(git_repo, "v1.2.0-rc", base_sha)
    _tag(git_repo, "v1.2.0", base_sha)
    window = SinceDeployWindow(FakeMirror(git_repo), collector, BranchRole.STAGING)

    before, after = await window.resolve("org/repo")

    assert before == "v1.2.0"
    assert after == "HEAD"


async def test_staging_picks_a_further_rc_after_the_full_release(git_repo, collector):
    base_sha = _commit("base", cwd=git_repo)
    _tag(git_repo, "v1.2.0-rc", base_sha)
    _tag(git_repo, "v1.2.0", base_sha)
    _tag(git_repo, "v1.3.0-rc", base_sha)
    window = SinceDeployWindow(FakeMirror(git_repo), collector, BranchRole.STAGING)

    before, _ = await window.resolve("org/repo")

    assert before == "v1.3.0-rc"


async def test_semver_aware_selection_prefers_v1_10_0_over_v1_9_0(git_repo, collector):
    base_sha = _commit("base", cwd=git_repo)
    _tag(git_repo, "v1.9.0", base_sha)
    _tag(git_repo, "v1.10.0", base_sha)
    window = SinceDeployWindow(FakeMirror(git_repo), collector, BranchRole.STAGING)

    before, _ = await window.resolve("org/repo")

    assert before == "v1.10.0"


async def test_non_version_tags_are_ignored(git_repo, collector):
    base_sha = _commit("base", cwd=git_repo)
    _tag(git_repo, "v1.2.0", base_sha)
    _tag(git_repo, "nightly", base_sha)
    _tag(git_repo, "build-42", base_sha)
    window = SinceDeployWindow(FakeMirror(git_repo), collector, BranchRole.STAGING)

    before, _ = await window.resolve("org/repo")

    assert before == "v1.2.0"


async def test_no_tag_resolves_to_root_for_staging_and_release(git_repo, collector):
    _commit("base", cwd=git_repo)

    staging_window = SinceDeployWindow(FakeMirror(git_repo), collector, BranchRole.STAGING)
    release_window = SinceDeployWindow(FakeMirror(git_repo), collector, BranchRole.RELEASE)

    staging_before, _ = await staging_window.resolve("org/repo")
    release_before, _ = await release_window.resolve("org/repo")

    assert staging_before == EMPTY_TREE_SHA
    assert release_before == EMPTY_TREE_SHA


async def test_release_picks_the_last_full_release(git_repo, collector):
    base_sha = _commit("base", cwd=git_repo)
    _tag(git_repo, "v1.1.0", base_sha)
    _tag(git_repo, "v1.2.0", base_sha)
    window = SinceDeployWindow(FakeMirror(git_repo), collector, BranchRole.RELEASE)

    before, _ = await window.resolve("org/repo")

    assert before == "v1.2.0"


async def test_release_ignores_a_higher_rc_while_staging_picks_it(git_repo, collector):
    base_sha = _commit("base", cwd=git_repo)
    _tag(git_repo, "v1.2.0", base_sha)
    _tag(git_repo, "v1.3.0-rc", base_sha)

    release_window = SinceDeployWindow(FakeMirror(git_repo), collector, BranchRole.RELEASE)
    staging_window = SinceDeployWindow(FakeMirror(git_repo), collector, BranchRole.STAGING)

    release_before, _ = await release_window.resolve("org/repo")
    staging_before, _ = await staging_window.resolve("org/repo")

    assert release_before == "v1.2.0"
    assert staging_before == "v1.3.0-rc"


async def test_resolve_goes_through_the_injected_collector(git_repo):
    stub = StubCollector(("v1.0.0", "v1.1.0"))
    window = SinceDeployWindow(FakeMirror(git_repo), stub, BranchRole.STAGING)

    before, _ = await window.resolve("org/repo")

    assert before == "v1.1.0"
    assert stub.list_tags_calls == [str(git_repo)]


async def test_unsupported_environment_raises(git_repo, collector):
    window = SinceDeployWindow(FakeMirror(git_repo), collector, BranchRole.DEV)

    with pytest.raises(ValueError):
        await window.resolve("org/repo")
