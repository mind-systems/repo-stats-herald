import base64
import contextlib
import os
import subprocess
import tempfile
import threading
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager
from pathlib import Path
from urllib.parse import urlsplit

from src.github.app_auth import GitHubAppAuth

_HTTP_SCHEMES = {"http", "https"}


class RepoMirror:
    """Worktree-per-operation off one per-repo bare object store at a pinned
    ref — concurrent operations for the same repo never share a mutable
    checkout. A finished worktree is reclaimed the next time `ensure` runs
    for its repo (see the note on `tree` for why reclamation is deferred
    rather than immediate).

    Composition-root assembly (not wired yet — no caller exists above this
    task): read `Settings`, load the App private key PEM from
    `github_app_private_key_path`, build `GitHubAppAuth(github_app_id, pem)`,
    then `RepoMirror(Path(mirror_root), auth, clone_source=<builds the repo's
    HTTPS clone URL>)`. Before that first construction, the consuming task
    must assert `github_app_id`, `github_app_private_key_path`, and
    `mirror_root` are actually set — `Settings`' defaults only keep
    `Settings()` constructible for the webhook test suite; without this
    assertion a misconfigured deployment would surface as a `None`-typed
    error deep inside token minting instead of a clear boot failure. That
    same startup path should also sweep `{mirror_root}/worktrees` (remove
    every entry, then `git worktree prune` per repo) — `tree()`'s deferred
    reclamation lives in an in-memory list, so worktrees finished right
    before a crash/restart are never picked up by `ensure()` and would
    otherwise leak on disk indefinitely.
    """

    def __init__(
        self,
        mirror_root: Path,
        auth: GitHubAppAuth,
        clone_source: Callable[[str, int], str],
    ) -> None:
        self._mirror_root = mirror_root
        self._auth = auth
        self._clone_source = clone_source
        self._finished_worktrees: list[tuple[Path, Path]] = []
        self._finished_worktrees_lock = threading.Lock()

    def _bare_path(self, repo: str) -> Path:
        return self._mirror_root / f"{repo}.git"

    def _worktrees_root(self) -> Path:
        return self._mirror_root / "worktrees"

    def ensure(self, repo: str, org_id: int) -> None:
        self._mirror_root.mkdir(parents=True, exist_ok=True)
        bare_path = self._bare_path(repo)
        source = self._clone_source(repo, org_id)
        credential = self._credential_for(source, org_id)

        if not bare_path.exists():
            self._run_git(
                "clone", "--mirror", source, str(bare_path),
                cwd=self._mirror_root,
                credential=credential,
            )
        else:
            self._run_git(
                "fetch", "--prune", "origin",
                cwd=bare_path,
                credential=credential,
            )

        self._reclaim_finished_worktrees(bare_path)

        # Reaps worktree metadata whose directory is already gone (e.g. a
        # crash before reclamation ran) — never touches a live worktree.
        self._run_git("worktree", "prune", cwd=bare_path)

    @contextlib.contextmanager
    def tree(self, repo: str, org_id: int, ref: str) -> Iterator[Path]:
        """Checks out `ref` into its own scratch worktree and yields its path.

        Reclamation of the worktree is deferred to the next `ensure()` call
        for this repo rather than run here in `finally`: `git worktree
        remove` (even with a prior `mkdtemp`-created, otherwise-empty
        directory) deletes the checkout from disk as part of removing it,
        which would pull the ground from under a caller that's still holding
        (or just released) the yielded `Path` — e.g. a consumer that reads
        the tree's content in a background thread and returns the path for
        the orchestrating call to inspect afterwards. Deferring the actual
        `git worktree remove` to the repo's next `ensure()` keeps every
        already-yielded path valid until that point, while still bounding
        the leak to "worktrees opened since the last `ensure()`" instead of
        growing without limit.
        """
        bare_path = self._bare_path(repo)
        worktrees_root = self._worktrees_root()
        worktrees_root.mkdir(parents=True, exist_ok=True)
        scratch = Path(tempfile.mkdtemp(prefix="wt-", dir=worktrees_root))

        self._run_git(
            "worktree", "add", "--detach", str(scratch), ref,
            cwd=bare_path,
        )
        try:
            yield scratch
        finally:
            with self._finished_worktrees_lock:
                self._finished_worktrees.append((bare_path, scratch))

    def _reclaim_finished_worktrees(self, bare_path: Path) -> None:
        with self._finished_worktrees_lock:
            due = [scratch for (bare, scratch) in self._finished_worktrees if bare == bare_path]
            self._finished_worktrees = [
                entry for entry in self._finished_worktrees if entry[0] != bare_path
            ]

        for scratch in due:
            # Guarded so one worktree's removal failure can't mask another's
            # or abort `ensure()` over a stale, already-gone directory.
            with contextlib.suppress(subprocess.CalledProcessError):
                self._run_git(
                    "worktree", "remove", "--force", str(scratch),
                    cwd=bare_path,
                )
            if scratch.exists():
                with contextlib.suppress(OSError):
                    scratch.rmdir()

    def _credential_for(self, source: str, org_id: int) -> str | None:
        scheme = urlsplit(source).scheme
        if scheme not in _HTTP_SCHEMES:
            return None
        return self._auth.token(org_id)

    def _run_git(self, *args: str, cwd: Path, credential: str | None = None) -> None:
        env = None
        if credential is not None:
            basic = base64.b64encode(f"x-access-token:{credential}".encode()).decode()
            # Passed via env, not `-c ...`/argv: argv lands in the process
            # table (world-readable via /proc/<pid>/cmdline) and verbatim in
            # `CalledProcessError.cmd` on failure — env vars are readable
            # only by the process owner/root and never appear in that
            # exception.
            env = {
                **os.environ,
                "GIT_CONFIG_COUNT": "1",
                "GIT_CONFIG_KEY_0": "http.extraHeader",
                "GIT_CONFIG_VALUE_0": f"Authorization: Basic {basic}",
            }
        subprocess.run(["git", *args], cwd=cwd, env=env, check=True, capture_output=True)
