import logging
from pathlib import Path

from src.knowledge.chunker import chunk_markdown
from src.knowledge.source_strategy import SourceStrategy
from src.knowledge.store import Chunk, KnowledgeStore
from src.llm.embedder import Embedder

logger = logging.getLogger(__name__)


class ArtifactIndexer:
    """Reads a selected source from an isolated mirror tree, chunks it,
    embeds it, and upserts it into the knowledge store — the read → chunk →
    embed → upsert path for one source.

    Assembled at the composition root from the injected strategy, embedder,
    and store; it never constructs a concrete client itself.
    """

    def __init__(
        self,
        strategy: SourceStrategy,
        embedder: Embedder,
        store: KnowledgeStore,
    ) -> None:
        self._strategy = strategy
        self._embedder = embedder
        self._store = store

    async def index(self, repo: str, path: str, tree: Path) -> None:
        if not self._strategy.selects(path):
            logger.debug("skipping %s:%s — not selected", repo, path)
            return

        try:
            text = (tree / path).read_text(encoding="utf-8")
        except UnicodeDecodeError:
            logger.debug("skipping %s:%s — not valid UTF-8", repo, path)
            return

        chunks = chunk_markdown(text)
        embeddings = await self._embedder.embed(chunks)
        items = [
            Chunk(content=content, embedding=embedding)
            for content, embedding in zip(chunks, embeddings, strict=True)
        ]

        await self._store.upsert(repo, path, items)
        logger.info("indexed %s:%s — %d chunks", repo, path, len(items))

    async def remove(self, repo: str, path: str) -> None:
        await self._store.delete(repo, path)
