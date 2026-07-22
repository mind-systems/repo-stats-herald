import logging

from src.commits.collector import GitCommitCollector
from src.episodic.linked_change import LinkedChangeResolver
from src.episodic.models import EpisodicEntry
from src.episodic.store import EpisodicStore
from src.github.mirror import RepoMirror
from src.llm.embedder import Embedder

logger = logging.getLogger(__name__)


class EpisodicBackfill:
    """Replays a served repo's full first-parent history through the
    linked-change resolver, appending one episodic entry per historical
    commit with the commit's own timestamp.

    Resolve + embed only — no per-change LLM generation. Reads the bare
    object store directly (no worktree per step), the deliberate exception
    to the mirror's worktree-per-operation model for this read-only replay.
    Idempotent across re-runs: a step whose `after` SHA is already recorded
    for the repo (by a prior backfill run or a live push) is skipped.

    Constructor DI: assembled at the composition root from the injected
    mirror, resolver, embedder, store, and collector, plus the canonical-ref
    policy; it never builds a concrete client itself. Self-contained — calls
    `mirror.ensure` itself rather than relying on another task having run.
    """

    def __init__(
        self,
        mirror: RepoMirror,
        resolver: LinkedChangeResolver,
        embedder: Embedder,
        store: EpisodicStore,
        collector: GitCommitCollector,
        canonical_refs: dict[str, str],
    ) -> None:
        self._mirror = mirror
        self._resolver = resolver
        self._embedder = embedder
        self._store = store
        self._collector = collector
        self._canonical_refs = canonical_refs

    def _canonical_ref(self, repo: str) -> str:
        override = self._canonical_refs.get(repo)
        if override is not None:
            return override
        return self._mirror.default_branch(repo)

    async def run(self, repo: str, org_id: int) -> None:
        self._mirror.ensure(repo, org_id)
        canonical = self._canonical_ref(repo)
        bare = str(self._mirror.object_store_path(repo))

        recorded = await self._store.recorded_commit_shas(repo)
        steps = self._collector.first_parent_steps(bare, canonical)

        walked = 0
        appended = 0
        skipped = 0
        for before, after in steps:
            walked += 1
            if after in recorded:
                skipped += 1
                continue

            change = self._resolver.resolve(bare, before, after)
            content = "\n".join([*change.completed_tasks, *(c.message for c in change.commits.commits)])
            if not content:
                logger.debug("skipping empty step: repo=%s after=%s", repo, after)
                skipped += 1
                continue

            changed_at = self._collector.commit_timestamp(bare, after)
            [embedding] = await self._embedder.embed([content])

            entry = EpisodicEntry(
                repo=repo,
                org_id=org_id,
                completed_tasks=change.completed_tasks,
                commit_shas=tuple(c.sha for c in change.commits.commits),
                content=content,
                embedding=embedding,
                changed_at=changed_at,
            )
            await self._store.append(entry)
            recorded.add(after)
            appended += 1

        logger.info(
            "episodic backfill complete: repo=%s commits_walked=%d entries_appended=%d skipped=%d",
            repo,
            walked,
            appended,
            skipped,
        )
