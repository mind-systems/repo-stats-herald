from src.changelog.report import ReportWindow
from src.commits.collector import EMPTY_TREE_SHA, GitCommitCollector
from src.github.mirror import RepoMirror
from src.routing.models import BranchRole
from src.versioning.versioner import Version


class SinceDeployWindow(ReportWindow):
    """A `ReportWindow` that anchors `before` to the last deploy tag for an
    `environment` (`BranchRole`), read through the shared
    `GitCommitCollector.list_tags` primitive — the same tag list `Versioner`
    reads, so both agree on what counts as a version tag and how they order.

    Like `ReportWindow.resolve` in general, `resolve` never calls
    `mirror.ensure`: it reads the already-ensured bare mirror at
    `mirror.object_store_path(repo)`.
    """

    def __init__(self, mirror: RepoMirror, collector: GitCommitCollector, environment: BranchRole) -> None:
        self.mirror = mirror
        self.collector = collector
        self.environment = environment

    async def resolve(self, repo: str) -> tuple[str, str]:
        if self.environment not in (BranchRole.RELEASE, BranchRole.STAGING):
            raise ValueError(f"unsupported environment: {self.environment!r}")

        bare = str(self.mirror.object_store_path(repo))
        tags = self.collector.list_tags(bare)
        parsed: list[tuple[Version, str]] = [
            (v, tag) for tag in tags if (v := Version.parse(tag)) is not None
        ]

        if self.environment is BranchRole.RELEASE:
            candidates = [(version, tag) for version, tag in parsed if not version.prerelease]
        else:
            candidates = parsed

        if not candidates:
            before = EMPTY_TREE_SHA
        else:
            _, before = max(candidates, key=lambda pair: pair[0])

        after = "HEAD"
        return before, after
