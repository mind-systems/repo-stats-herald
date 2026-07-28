import os
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

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


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """A throwaway local git repo, pinned committer identity and branch name
    so the fixture is reproducible without relying on ambient git config."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git("init", "-q", "-b", _TRUNK, cwd=repo)
    return repo


@pytest.fixture
def commit_at() -> Callable[..., str]:
    """Commits (allow-empty) into `repo`, optionally at an explicit
    author/committer timestamp (ISO 8601, e.g. `"2020-01-01T00:00:00+00:00"`)
    so tests can place commits at controlled points relative to `now`.
    Returns the new commit's SHA."""

    def _commit_at(repo: Path, message: str, when: str | None = None) -> str:
        return _commit(message, cwd=repo, when=when)

    return _commit_at
