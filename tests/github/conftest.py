"""Fixtures for the mirror isolation and auth single-flight contract tests.

These tests are red against the `RepoMirror`/`GitHubAppAuth` stubs and must
fail because the mirror/auth logic is absent, never because of an import or
fixture error.
"""

import subprocess
from collections import namedtuple
from pathlib import Path

import pytest

from src.github.app_auth import GitHubAppAuth
from src.github.mirror import RepoMirror

LocalUpstream = namedtuple("LocalUpstream", ["path", "ref_a", "ref_b"])

_REF_A = "trunk"
_REF_B = "feature"


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _commit(message: str, cwd: Path) -> None:
    _git(
        "-c",
        "user.name=herald-test",
        "-c",
        "user.email=herald@test.invalid",
        "commit",
        "-q",
        "-m",
        message,
        cwd=cwd,
    )


@pytest.fixture
def local_upstream(tmp_path: Path) -> LocalUpstream:
    """Builds a throwaway local git repo with two branches whose working
    trees hold distinguishable content (differing bytes in the same file).

    Pins committer identity and branch names explicitly so the fixture is
    reproducible without relying on the developer's ambient git config
    (global user.name/user.email, init.defaultBranch)."""
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    _git("init", "-q", "-b", _REF_A, cwd=upstream)

    marker = upstream / "marker.txt"
    marker.write_text("content-a")
    _git("add", "marker.txt", cwd=upstream)
    _commit("commit on ref a", cwd=upstream)

    _git("checkout", "-q", "-b", _REF_B, cwd=upstream)
    marker.write_text("content-b")
    _git("add", "marker.txt", cwd=upstream)
    _commit("commit on ref b", cwd=upstream)

    return LocalUpstream(path=upstream, ref_a=_REF_A, ref_b=_REF_B)


@pytest.fixture
def auth() -> GitHubAppAuth:
    return GitHubAppAuth(app_id=1, private_key="test-key")


@pytest.fixture
def mirror(tmp_path: Path, local_upstream: LocalUpstream, auth: GitHubAppAuth) -> RepoMirror:
    return RepoMirror(
        mirror_root=tmp_path / "mirror",
        auth=auth,
        clone_source=lambda repo, org_id: str(local_upstream.path),
    )
