import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.changelog.report import Report, TimeWindow
from src.changelog.sections.per_branch import PerBranchSection
from src.commits.collector import EMPTY_TREE_SHA, GitCommitCollector
from src.episodic.linked_change import LinkedChangeResolver
from src.github.app_auth import GitHubAppAuth
from src.github.mirror import RepoMirror
from src.knowledge.source_strategy import AiFactorySourceStrategy

_TRUNK = "main"


def _git(*args: str, cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True, env=env)


def _commit(message: str, cwd: Path, when: str | None = None) -> str:
    env = None
    if when is not None:
        env = {**os.environ, "GIT_AUTHOR_DATE": when, "GIT_COMMITTER_DATE": when}
    _git(
        "-c", "user.name=herald-test",
        "-c", "user.email=herald@test.invalid",
        "commit", "-q", "--allow-empty", "-m", message,
        cwd=cwd, env=env,
    )
    return _git("rev-parse", "HEAD", cwd=cwd).stdout.strip()


class FakeReasoner:
    """Minimal narrate-only stand-in for `PerBranchSection`'s reasoner
    collaborator — these tests exercise the git-range/empty-tree paths
    around `TimeWindow.resolve`, never the LLM boundary."""

    async def narrate(self, change, lang: str = "ru") -> str:
        return "narrated"


@pytest.fixture
def mirror_for(tmp_path: Path):
    """Builds a `RepoMirror` rooted at `tmp_path`, plus a helper that
    materializes a plain (non-bare) git repo directly at the path
    `RepoMirror.object_store_path`/`default_branch` expect. `ensure()` is
    never called by these tests, so no network/auth is exercised — only
    read-only git-range resolution over an already-"mirrored" repo."""
    mirror_root = tmp_path / "mirror"
    auth = GitHubAppAuth(app_id=1, private_key="test-key")
    mirror = RepoMirror(mirror_root, auth, clone_source=lambda repo, org_id: "")

    def _make_repo(repo_name: str) -> Path:
        repo_path = mirror_root / f"{repo_name}.git"
        repo_path.mkdir(parents=True)
        _git("init", "-q", "-b", _TRUNK, cwd=repo_path)
        return repo_path

    return mirror, _make_repo


async def test_resolve_active_window_returns_range_with_in_window_commits(mirror_for):
    mirror, make_repo = mirror_for
    repo_path = make_repo("active")
    now = datetime.now(timezone.utc)
    old_sha = _commit("old", cwd=repo_path, when=(now - timedelta(days=10)).isoformat())
    new_sha = _commit("new", cwd=repo_path, when=(now - timedelta(hours=1)).isoformat())

    window = TimeWindow(timedelta(days=1), mirror=mirror, collector=GitCommitCollector(), canonical_refs={})

    before, after = await window.resolve("active")

    assert after == new_sha
    assert before == old_sha
    assert before != after


async def test_resolve_window_older_than_last_commit_yields_empty_range(mirror_for):
    mirror, make_repo = mirror_for
    repo_path = make_repo("quiet")
    now = datetime.now(timezone.utc)
    sha = _commit("only", cwd=repo_path, when=(now - timedelta(days=30)).isoformat())

    window = TimeWindow(timedelta(days=1), mirror=mirror, collector=GitCommitCollector(), canonical_refs={})

    before, after = await window.resolve("quiet")

    assert before == after == sha


async def test_resolve_falls_back_to_empty_tree_when_whole_history_younger_than_delta(mirror_for):
    mirror, make_repo = mirror_for
    repo_path = make_repo("young")
    sha = _commit("only", cwd=repo_path)

    window = TimeWindow(timedelta(days=3650), mirror=mirror, collector=GitCommitCollector(), canonical_refs={})

    before, after = await window.resolve("young")

    assert before == EMPTY_TREE_SHA
    assert after == sha


async def test_report_build_over_young_repo_does_not_raise(mirror_for):
    """Whole history younger than `delta`: `before = EMPTY_TREE_SHA`, a real
    `after`. `PerBranchSection` must render (via `active_branches`'
    empty-tree-safe `before` handling) without raising."""
    mirror, make_repo = mirror_for
    repo_path = make_repo("young-branch")
    _commit("only", cwd=repo_path)
    collector = GitCommitCollector()
    resolver = LinkedChangeResolver(collector, AiFactorySourceStrategy())
    window = TimeWindow(timedelta(days=3650), mirror=mirror, collector=collector, canonical_refs={})
    section = PerBranchSection(mirror, collector, resolver, FakeReasoner())
    report = Report(window, [section])

    result = await report.build("young-branch", org_id=1)

    assert result is not None
    assert "narrated" in result


async def test_report_build_over_empty_repo_returns_none_without_raising(mirror_for):
    """No commits at all: `before = after = EMPTY_TREE_SHA`. `PerBranchSection`
    must see this as "no active branches" (via `active_branches`'
    `after == EMPTY_TREE_SHA` guard) and `Report.build` returns `None`
    rather than raising."""
    mirror, make_repo = mirror_for
    make_repo("empty")
    collector = GitCommitCollector()
    resolver = LinkedChangeResolver(collector, AiFactorySourceStrategy())
    window = TimeWindow(timedelta(days=1), mirror=mirror, collector=collector, canonical_refs={})
    section = PerBranchSection(mirror, collector, resolver, FakeReasoner())
    report = Report(window, [section])

    result = await report.build("empty", org_id=1)

    assert result is None
