import logging

from src.github.mirror import RepoMirror, resolve_canonical_ref
from src.graph.coordination import CoordinationSeeder
from src.ingestion.models import PushEvent
from src.knowledge.indexer import ArtifactIndexer
from src.knowledge.source_strategy import SourceStrategy

logger = logging.getLogger(__name__)


class KnowledgeSync:
    """Populates a served repo's knowledge store on first sight (`backfill`)
    and keeps it current on every push to the repo's canonical ref
    (`on_push`) — a push to any other ref touches no semantic memory.

    Constructor DI: assembled at the composition root from the injected
    mirror, indexer, and strategy; it never builds a concrete client itself.
    """

    def __init__(
        self,
        mirror: RepoMirror,
        indexer: ArtifactIndexer,
        strategy: SourceStrategy,
        canonical_refs: dict[str, str],
        seeder: CoordinationSeeder | None = None,
    ) -> None:
        self._mirror = mirror
        self._indexer = indexer
        self._strategy = strategy
        self._canonical_refs = canonical_refs
        self._seeder = seeder

    def _canonical_ref(self, repo: str) -> str:
        return resolve_canonical_ref(repo, self._canonical_refs, self._mirror)

    async def backfill(self, repo: str, org_id: int) -> None:
        self._mirror.ensure(repo, org_id)
        canonical = self._canonical_ref(repo)

        seen = 0
        with self._mirror.tree(repo, org_id, canonical) as tree:
            for path in tree.rglob("*"):
                if not path.is_file() or ".git" in path.parts:
                    continue
                relative = path.relative_to(tree).as_posix()
                await self._indexer.index(repo, relative, tree)
                seen += 1

        logger.info("backfill complete: repo=%s ref=%s files_seen=%d", repo, canonical, seen)

        if self._seeder is not None:
            await self._seeder.seed(repo, org_id)

    async def on_push(self, push: PushEvent) -> None:
        self._mirror.ensure(push.repo, push.org_id)
        canonical = self._canonical_ref(push.repo)

        if push.branch != canonical:
            logger.debug(
                "skipping non-canonical push: repo=%s branch=%s canonical=%s",
                push.repo,
                push.branch,
                canonical,
            )
            return

        changed_paths: set[str] = set()
        for commit in push.commits:
            changed_paths.update(commit.added)
            changed_paths.update(commit.modified)
            changed_paths.update(commit.removed)

        indexed = 0
        removed = 0
        with self._mirror.tree(push.repo, push.org_id, push.after) as tree:
            for path in changed_paths:
                if (tree / path).is_file():
                    await self._indexer.index(push.repo, path, tree)
                    indexed += 1
                elif self._strategy.selects(path):
                    await self._indexer.remove(push.repo, path)
                    removed += 1

        logger.info(
            "on_push complete: repo=%s ref=%s indexed=%d removed=%d",
            push.repo,
            canonical,
            indexed,
            removed,
        )

        if self._seeder is not None:
            await self._seeder.seed(push.repo, push.org_id)
