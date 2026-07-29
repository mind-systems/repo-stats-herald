"""Fixtures for the mirror lifecycle, credential, and isolation test
modules.

`local_upstream` builds a throwaway two-branch git repo whose branches hold
distinguishable content; `auth` builds a `GitHubAppAuth` with no signing
consulted unless a test opts in; `mirror` wires a `RepoMirror` straight to
`local_upstream`'s plain filesystem path, with the real `subprocess.run` and
no token minting involved.

`GatedRunner` and `build_gated_mirror` (used only by the forced-interleaving
concurrency scenarios) let a test force a deterministic interleaving over
genuine git subprocesses: `GatedRunner` wraps real `subprocess.run`, and
`build_gated_mirror` wires a `RepoMirror` to one the same way the `mirror`
fixture wires one to the plain `subprocess.run`.
"""

import subprocess
import threading
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


class GatedRunner:
    """Wraps real `subprocess.run` so a concurrency test can force a
    deterministic interleaving of genuine git subprocesses — the git
    commands actually execute against `local_upstream`, so worktrees, refs
    and content are real; only *when* a selected command runs is under the
    test's control.

    Every dispatched command is recorded in full (its argv), regardless of
    whether it is gated, so a test can assert e.g. how many times `clone`
    was dispatched. `add_gate` registers a gate on a git subcommand — a
    single element such as `"clone"` matches on the command's first
    argument after `git`, a tuple such as `("worktree", "add")` matches
    that specific subcommand pair, so a test can hold one thread on one
    subcommand while another proceeds on a different one. When a
    dispatched command matches a registered gate, the runner first sets
    that gate's `reached` event — so the test knows a thread has arrived at
    the gated command — then blocks on the `release` primitive the test
    supplied (a `threading.Event` for a single hold, or a
    `threading.Barrier` to force two threads to arrive before either is let
    through) before the real subprocess actually runs. Only `threading`
    primitives are used for the hold, never `sleep`, so the forced
    interleaving is deterministic rather than racy. `clear_gates` drops
    every registered gate once the forced section is over, so a test can
    keep driving the mirror single-threaded afterwards (e.g. to flush
    deferred cleanup) without re-tripping a multi-party gate that would
    otherwise wait forever for a second thread that is never coming.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.calls: list[list[str]] = []
        self._gates: dict[tuple[str, ...], tuple[threading.Event, object]] = {}

    def add_gate(self, *subcommand: str, release: object) -> threading.Event:
        reached = threading.Event()
        self._gates[tuple(subcommand)] = (reached, release)
        return reached

    def clear_gates(self) -> None:
        """Drops every registered gate. A test calls this once its forced
        interleaving is over, before it drives the mirror any further on a
        single thread — otherwise a later solo call would hit a gate whose
        `release` is a multi-party `Barrier` and block forever waiting for a
        second party that will never arrive.
        """
        self._gates.clear()

    def __call__(self, *args, **kwargs) -> subprocess.CompletedProcess:
        argv = args[0]
        with self._lock:
            self.calls.append(list(argv))

        command = tuple(argv[1:])
        for key, (reached, release) in self._gates.items():
            if command[: len(key)] == key:
                reached.set()
                release.wait()
                break

        return subprocess.run(*args, **kwargs)


def build_gated_mirror(
    mirror_root: Path,
    local_upstream: LocalUpstream,
    auth: GitHubAppAuth,
    runner: GatedRunner,
) -> RepoMirror:
    """Builds a `RepoMirror` wired to `runner` in place of the real
    `subprocess.run`, cloning from the same plain filesystem path the
    `mirror` fixture uses — for the forced-interleaving scenarios that need
    to control when a git subcommand actually executes.
    """
    return RepoMirror(
        mirror_root=mirror_root,
        auth=auth,
        clone_source=lambda repo, org_id: str(local_upstream.path),
        run=runner,
    )
