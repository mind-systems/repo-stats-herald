import dataclasses

from src.changelog.section import ReportSection
from src.episodic.linked_change import LinkedChangeResolver
from src.github.mirror import RepoMirror
from src.reasoning.reasoner import Reasoner


class SummarySection(ReportSection):
    """The holistic shipped-story section: narrates the whole `(before,
    after)` range as a single `Reasoner.narrate` call, so cross-project
    "unblocks" reach comes from the reasoner's own neighbor retrieval — this
    section runs no separate neighbor/narrator path and does not read open
    roadmap tasks (that is `RemainingSection`'s job).
    """

    def __init__(
        self,
        mirror: RepoMirror,
        resolver: LinkedChangeResolver,
        reasoner: Reasoner,
    ) -> None:
        self._mirror = mirror
        self._resolver = resolver
        self._reasoner = reasoner

    async def render(
        self, repo: str, org_id: int, before: str, after: str, lang: str = "ru"
    ) -> str | None:
        bare = str(self._mirror.object_store_path(repo))
        change = self._resolver.resolve(bare, before, after)

        if not change.commits.commits:
            return None

        # Rebind the bare filesystem path the resolver stored back to the
        # bare repo KEY: the knowledge/episodic stores (and `narrate`'s
        # retrieval scoping) are keyed by that KEY, not by a filesystem
        # path, which would otherwise scope retrieval to zero rows.
        change = dataclasses.replace(change, repo=repo)
        return await self._reasoner.narrate(change, lang)
