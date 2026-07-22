from collections.abc import Callable
from contextlib import AbstractContextManager
from pathlib import Path

from src.github.app_auth import GitHubAppAuth


class RepoMirror:
    """Worktree-per-operation off one per-repo bare object store at a pinned
    ref, torn down on exit — concurrent operations for the same repo never
    share a mutable checkout."""

    def __init__(
        self,
        mirror_root: Path,
        auth: GitHubAppAuth,
        clone_source: Callable[[str, int], str],
    ) -> None:
        self._mirror_root = mirror_root
        self._auth = auth
        self._clone_source = clone_source

    def ensure(self, repo: str, org_id: int) -> None:
        raise NotImplementedError

    def tree(self, repo: str, org_id: int, ref: str) -> AbstractContextManager[Path]:
        raise NotImplementedError
