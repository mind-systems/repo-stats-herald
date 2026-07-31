import asyncio
import base64
import contextlib
import os
import shutil
import subprocess
import tempfile
import threading
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractContextManager
from pathlib import Path
from typing import ParamSpec, TypeVar
from urllib.parse import urlsplit

from src.github.app_auth import GitHubAppAuth

_P = ParamSpec("_P")
_R = TypeVar("_R")

_HTTP_SCHEMES = {"http", "https"}


class RepoMirror:
    """Worktree-per-operation off one per-repo bare object store at a pinned
    ref — concurrent operations for the same repo never share a mutable
    checkout. A finished worktree is reclaimed the next time `ensure` runs
    for its repo (see the note on `tree` for why reclamation is deferred
    rather than immediate).

    Every method that shells out to `git` is `async` — the subprocess itself
    runs off the event loop, on a thread `RepoMirror` owns internally
    (`_to_thread`), so a long `clone`/`fetch` never stalls it. `ensure` holds
    a lazily-created per-repo `asyncio.Lock` across its whole body, so two
    concurrent `ensure` calls for the same never-cloned repo can't both pass
    the "no clone yet" check and both dispatch `git clone`; `tree` takes no
    such lock and can run for a repo while that repo's `ensure` is also
    in flight — git itself keeps a live worktree and an overlapping
    fetch/prune safe.

    Composition-root assembly (`src/main.py`'s `lifespan`, gated on the
    GitHub-App + mirror settings being present): read `Settings`, load the
    App private key PEM from `github_app_private_key_path`, build
    `GitHubAppAuth(github_app_id, pem)`, then `RepoMirror(Path(mirror_root),
    auth, clone_source=<builds the repo's HTTPS clone URL>)`. `Settings`'
    defaults only keep `Settings()` constructible for the webhook test suite
    (which builds `TestClient(app)` without running `lifespan`); the root
    itself gates assembly on the required settings and logs a warning
    instead when they are absent, rather than surfacing a `None`-typed error
    deep inside token minting. The same startup path calls
    `sweep_worktrees()` once before any `ensure()` — `tree()`'s deferred
    reclamation lives in an in-memory list, so worktrees finished right
    before a crash/restart are never picked up by `ensure()` and would
    otherwise leak on disk indefinitely.
    """

    def __init__(
        self,
        mirror_root: Path,
        auth: GitHubAppAuth,
        clone_source: Callable[[str, int], str],
        run: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    ) -> None:
        self._mirror_root = mirror_root
        self._auth = auth
        self._clone_source = clone_source
        self._run = run
        self._finished_worktrees: list[tuple[Path, Path]] = []
        self._finished_worktrees_lock = threading.Lock()
        self._ensure_locks: dict[str, asyncio.Lock] = {}

    def _bare_path(self, repo: str) -> Path:
        return self._mirror_root / f"{repo}.git"

    def _ensure_lock(self, repo: str) -> asyncio.Lock:
        """Lazily creates and returns `repo`'s serialization lock. Called
        only from synchronous code with no `await` in between the lookup and
        the insert, so two coroutines racing to create the same repo's lock
        can never both win — plain dict access on the event-loop thread is
        itself atomic with respect to other coroutines."""
        lock = self._ensure_locks.get(repo)
        if lock is None:
            lock = asyncio.Lock()
            self._ensure_locks[repo] = lock
        return lock

    def object_store_path(self, repo: str) -> Path:
        """Return `repo`'s bare object store path — the read-only entry
        point for history replay that intentionally bypasses the
        worktree-per-operation model: blobs are read by SHA (`git show`/`git
        log`/`git rev-list` against this path), never through a mutable
        checkout.

        The caller must have run `ensure(repo, ...)` first so the bare
        clone exists.
        """
        return self._bare_path(repo)

    def _worktrees_root(self) -> Path:
        return self._mirror_root / "worktrees"

    async def default_branch(self, repo: str) -> str:
        """Return `repo`'s default branch, read from its bare mirror's `HEAD`.

        The caller must have run `ensure(repo, ...)` first so the bare clone
        exists.
        """
        return await self._to_thread(self._default_branch_sync, repo)

    def _default_branch_sync(self, repo: str) -> str:
        result = self._run(
            ["git", "symbolic-ref", "--short", "HEAD"],
            cwd=self._bare_path(repo),
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()

    async def sweep_worktrees(self) -> None:
        """Startup reclamation: removes every entry under
        `{mirror_root}/worktrees` and runs `git worktree prune` per bare
        repo. `tree()`'s deferred reclamation lives in an in-memory list, so
        worktrees finished right before a crash/restart are never picked up
        by `ensure()` and would otherwise leak on disk indefinitely — this
        sweep is the consuming task's guard against that, run once at
        startup before any `ensure()` call.
        """
        worktrees_root = self._worktrees_root()
        if worktrees_root.exists():
            for entry in worktrees_root.iterdir():
                shutil.rmtree(entry, ignore_errors=True)

        if not self._mirror_root.exists():
            return
        for bare_path in self._mirror_root.glob("*.git"):
            with contextlib.suppress(subprocess.CalledProcessError):
                await self._run_git("worktree", "prune", cwd=bare_path)

    async def ensure(self, repo: str, org_id: int) -> None:
        """Clones `repo` on first sight, else fetches into its existing bare
        store. Serialized per repo behind a lazily-created `asyncio.Lock`
        held across the whole call, so two concurrent `ensure` coroutines
        for the same never-cloned repo can't both see no clone yet and both
        dispatch `git clone` — a clone is dispatched at most once per repo.
        """
        async with self._ensure_lock(repo):
            self._mirror_root.mkdir(parents=True, exist_ok=True)
            bare_path = self._bare_path(repo)
            source = self._clone_source(repo, org_id)
            credential = self._credential_for(source, org_id)

            if not bare_path.exists():
                await self._run_git(
                    "clone", "--mirror", source, str(bare_path),
                    cwd=self._mirror_root,
                    credential=credential,
                )
            else:
                await self._run_git(
                    "fetch", "--prune", "origin",
                    cwd=bare_path,
                    credential=credential,
                )

            await self._reclaim_finished_worktrees(bare_path)

            # Reaps worktree metadata whose directory is already gone (e.g. a
            # crash before reclamation ran) — never touches a live worktree.
            await self._run_git("worktree", "prune", cwd=bare_path)

    @contextlib.asynccontextmanager
    async def tree(self, repo: str, org_id: int, ref: str) -> AsyncIterator[Path]:
        """Checks out `ref` into its own scratch worktree and yields its path.

        Takes no per-repo lock — unlike `ensure`, a `tree` call is free to
        run for a repo whose `ensure` is concurrently in flight, and two
        `tree` calls for the same repo never contend with each other either;
        git's own worktree handling keeps both safe. A consumer may hold the
        yielded path open arbitrarily long (it is never held across this
        lock), which is also why `ensure` never takes it while checking out.

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

        await self._run_git(
            "worktree", "add", "--detach", str(scratch), ref,
            cwd=bare_path,
        )
        try:
            yield scratch
        finally:
            with self._finished_worktrees_lock:
                self._finished_worktrees.append((bare_path, scratch))

    async def _reclaim_finished_worktrees(self, bare_path: Path) -> None:
        with self._finished_worktrees_lock:
            due = [scratch for (bare, scratch) in self._finished_worktrees if bare == bare_path]
            self._finished_worktrees = [
                entry for entry in self._finished_worktrees if entry[0] != bare_path
            ]

        for scratch in due:
            # Guarded so one worktree's removal failure can't mask another's
            # or abort `ensure()` over a stale, already-gone directory.
            with contextlib.suppress(subprocess.CalledProcessError):
                await self._run_git(
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

    async def _run_git(self, *args: str, cwd: Path, credential: str | None = None) -> None:
        await self._to_thread(self._run_git_sync, *args, cwd=cwd, credential=credential)

    def _run_git_sync(self, *args: str, cwd: Path, credential: str | None = None) -> None:
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
        self._run(["git", *args], cwd=cwd, env=env, check=True, capture_output=True)

    async def _to_thread(self, func: Callable[_P, _R], *args: _P.args, **kwargs: _P.kwargs) -> _R:
        """The one place `RepoMirror` offloads blocking work onto a thread it
        owns — every shelling-out method routes through this (directly or via
        `_run_git`) rather than calling `asyncio.to_thread` itself, so the
        offload mechanism is never scattered across call sites."""
        return await asyncio.to_thread(func, *args, **kwargs)


async def resolve_canonical_ref(repo: str, canonical_refs: dict[str, str], mirror: RepoMirror) -> str:
    """The one home for the canonical-ref policy: `repo`'s configured
    override if `canonical_refs` has one, else its mirror's default branch.
    Every consumer that needs "the ref a served repo is canonical on" —
    knowledge sync, coordination seeding, episodic backfill, and report
    windows/delivery — resolves through this single function rather than
    keeping its own copy of the policy."""
    override = canonical_refs.get(repo)
    if override is not None:
        return override
    return await mirror.default_branch(repo)
