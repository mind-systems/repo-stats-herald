import re
from dataclasses import dataclass
from functools import total_ordering

from src.commits.collector import GitCommitCollector
from src.github.mirror import RepoMirror
from src.routing.models import BranchRole

# Optional leading `v`, MAJOR.MINOR.PATCH, optional `-rc` suffix — no
# numeric `-rc.N` counter, matching the one form `Version.__str__` ever
# renders.
_VERSION_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(-rc)?$")


@total_ordering
@dataclass(frozen=True)
class Version:
    """A semver version with an optional `-rc` (release-candidate) marker —
    a boolean flag, never an `-rc.N` counter.

    `__str__` is the one canonical render path (`v1.2.0` / `v1.2.0-rc`);
    every consumer renders through it rather than formatting independently.
    Ordering is semver-aware over `(major, minor, patch)`, with a full
    release ranking above its own `-rc` at an equal base — never
    lexicographic, so `v1.10.0 > v1.9.0`.
    """

    major: int
    minor: int
    patch: int
    prerelease: bool = False

    def __str__(self) -> str:
        base = f"v{self.major}.{self.minor}.{self.patch}"
        return f"{base}-rc" if self.prerelease else base

    @classmethod
    def parse(cls, tag: str) -> "Version | None":
        """Parse a raw tag string into a `Version`, or `None` if it isn't
        one (e.g. `nightly`, `build-42`, `v1.2` with a missing component).
        Callers filter a tag list with `if (v := Version.parse(t)) is not
        None`."""
        match = _VERSION_RE.match(tag)
        if match is None:
            return None
        major, minor, patch, rc = match.groups()
        return cls(int(major), int(minor), int(patch), prerelease=rc is not None)

    def _sort_key(self) -> tuple[int, int, int, int]:
        # A full release ranks above its own `-rc` at an equal base.
        return (self.major, self.minor, self.patch, 0 if self.prerelease else 1)

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return self._sort_key() < other._sort_key()

    @property
    def base(self) -> "Version":
        """The full (non-prerelease) version sharing this version's
        major.minor.patch."""
        return Version(self.major, self.minor, self.patch, prerelease=False)

    @property
    def as_rc(self) -> "Version":
        """The `-rc` form sharing this version's major.minor.patch."""
        return Version(self.major, self.minor, self.patch, prerelease=True)

    def bump(self, component: str) -> "Version":
        """Bump one component and return a full (non-prerelease) version."""
        if component == "major":
            return Version(self.major + 1, 0, 0)
        if component == "minor":
            return Version(self.major, self.minor + 1, 0)
        if component == "patch":
            return Version(self.major, self.minor, self.patch + 1)
        raise ValueError(f"unknown version component: {component!r}")


class Versioner:
    """Derives the semver version a staging/release push carries, skipping
    back-merges that carry no staging-unique work.

    Constructor DI mirroring `src.episodic.backfill.EpisodicBackfill` /
    `src.knowledge.sync`: takes the already-assembled `RepoMirror` and
    `GitCommitCollector` rather than constructing either itself. Tags and
    history are read through `mirror.object_store_path(repo)` — the
    read-only bare object store, never a worktree.
    """

    def __init__(self, mirror: RepoMirror, collector: GitCommitCollector, version_increment: str) -> None:
        self._mirror = mirror
        self._collector = collector
        self._version_increment = version_increment

    def next(self, repo: str, role: BranchRole, before: str, after: str) -> Version | None:
        """The version `before..after` carries on `role`'s branch, or `None`
        for a staging push whose content is entirely a back-merge (no
        staging-unique non-merge work). `role` is taken as given — already
        classified by the caller (`role_for_branch`) — never re-derived from
        a raw branch name here."""
        bare = str(self._mirror.object_store_path(repo))
        tags = self._collector.list_tags(bare)
        parsed: list[tuple[Version, str]] = [
            (version, tag) for tag in tags if (version := Version.parse(tag)) is not None
        ]

        if role is BranchRole.STAGING:
            return self._next_staging(repo, bare, before, after, parsed)
        if role is BranchRole.RELEASE:
            return self._next_release(bare, after, parsed)

    def _next_staging(
        self,
        repo: str,
        bare: str,
        before: str,
        after: str,
        parsed: list[tuple[Version, str]],
    ) -> Version | None:
        exclude_ref = self._mirror.default_branch(repo)
        if not self._collector.new_commits(bare, before, after, exclude_ref):
            # A back-merge (fast-forward or via a merge commit) that brings
            # no staging-unique non-merge work — no bump, no spurious `-rc`.
            return None

        if not parsed:
            return Version(0, 1, 0, prerelease=True)

        basis = max(version for version, _ in parsed)
        return basis.bump(self._version_increment).as_rc

    def _next_release(self, bare: str, after: str, parsed: list[tuple[Version, str]]) -> Version:
        full_versions = [version for version, _ in parsed if not version.prerelease]
        last_full = max(full_versions) if full_versions else None

        rc_candidates = [
            (version, tag)
            for version, tag in parsed
            if version.prerelease and (last_full is None or version.base > last_full)
        ]
        reachable = [
            (version, tag) for version, tag in rc_candidates if self._collector.is_ancestor(bare, tag, after)
        ]
        if reachable:
            best_version, _ = max(reachable, key=lambda pair: pair[0])
            return best_version.base

        if last_full is not None:
            return last_full.bump(self._version_increment)

        return Version(0, 1, 0)
