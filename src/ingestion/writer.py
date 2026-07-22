import logging

from src.commits.collector import GitCommitCollector
from src.episodic.linked_change import LinkedChangeResolver
from src.episodic.models import EpisodicEntry
from src.episodic.store import EpisodicStore
from src.github.mirror import RepoMirror
from src.ingestion.models import PushEvent
from src.llm.embedder import Embedder

logger = logging.getLogger(__name__)


class EpisodicWriter:
    """Appends one `EpisodicEntry` per served push to the episodic log.

    Constructor DI: assembled at the composition root from the injected
    mirror, resolver, embedder, and store; it never builds a concrete client
    itself. Self-contained — calls `mirror.ensure` itself rather than relying
    on another background task having run first, so it produces an entry for
    every served push regardless of ordering with `KnowledgeSync`.
    """

    def __init__(
        self,
        mirror: RepoMirror,
        resolver: LinkedChangeResolver,
        embedder: Embedder,
        store: EpisodicStore,
        collector: GitCommitCollector,
    ) -> None:
        self._mirror = mirror
        self._resolver = resolver
        self._embedder = embedder
        self._store = store
        self._collector = collector

    async def write(self, push: PushEvent) -> None:
        self._mirror.ensure(push.repo, push.org_id)

        with self._mirror.tree(push.repo, push.org_id, push.after) as tree:
            change = self._resolver.resolve(str(tree), push.before, push.after)
            changed_at = self._collector.commit_timestamp(str(tree), push.after)

        content = "\n".join([*change.completed_tasks, *(c.message for c in change.commits.commits)])
        [embedding] = await self._embedder.embed([content])

        entry = EpisodicEntry(
            repo=push.repo,
            org_id=push.org_id,
            completed_tasks=change.completed_tasks,
            commit_shas=tuple(c.sha for c in change.commits.commits),
            content=content,
            embedding=embedding,
            changed_at=changed_at,
        )
        await self._store.append(entry)

        logger.info(
            "episodic write complete: repo=%s tasks=%d commits=%d",
            push.repo,
            len(entry.completed_tasks),
            len(entry.commit_shas),
        )
