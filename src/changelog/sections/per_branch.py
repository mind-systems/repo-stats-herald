import dataclasses

from src.changelog.section import ReportSection
from src.commits.collector import GitCommitCollector
from src.episodic.linked_change import LinkedChangeResolver
from src.github.mirror import RepoMirror
from src.reasoning.reasoner import Reasoner

_BRANCH_HEADER_TEMPLATE = "### {branch}"


class PerBranchSection(ReportSection):
    """The per-branch who-did-what section: one labelled sub-part per branch
    active in `(before, after)` (`GitCommitCollector.active_branches`), each
    narrated independently over its own branch-scoped range so a busy branch
    doesn't drown out a quiet one in a single combined narration.

    Two branches (e.g. an alias like `staging`/`master`, or a
    merged-but-undeleted feature branch sharing `main`'s tip) can resolve to
    the identical `(branch_before, branch_after)` range — deduped by that
    range so identical content is narrated (and billed to the LLM) once,
    under the first branch name the collector returned it for.
    """

    def __init__(
        self,
        mirror: RepoMirror,
        collector: GitCommitCollector,
        resolver: LinkedChangeResolver,
        reasoner: Reasoner,
    ) -> None:
        self._mirror = mirror
        self._collector = collector
        self._resolver = resolver
        self._reasoner = reasoner

    async def render(
        self, repo: str, org_id: int, before: str, after: str, lang: str = "ru"
    ) -> str | None:
        bare = str(self._mirror.object_store_path(repo))
        branches = self._collector.active_branches(bare, before, after)
        if not branches:
            return None

        # Iterate in the collector's returned order so section output order
        # is stable across runs.
        parts = []
        seen_ranges: set[tuple[str, str]] = set()
        for branch, branch_before, branch_after in branches:
            range_key = (branch_before, branch_after)
            if range_key in seen_ranges:
                continue
            seen_ranges.add(range_key)

            change = self._resolver.resolve(bare, branch_before, branch_after)
            if not change.commits.commits:
                # Defensive: active_branches already filters on in-window
                # commits, but a resolved range with no commits has nothing
                # for this branch to say.
                continue

            change = dataclasses.replace(change, repo=repo)
            narration = await self._reasoner.narrate(change, lang)
            parts.append(f"{_BRANCH_HEADER_TEMPLATE.format(branch=branch)}\n{narration}")

        if not parts:
            return None
        return "\n\n".join(parts)
