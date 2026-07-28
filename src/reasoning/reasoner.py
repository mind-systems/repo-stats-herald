import logging
from dataclasses import dataclass

from src.episodic.models import EpisodicEntry
from src.episodic.store import EpisodicStore
from src.knowledge.store import Chunk, KnowledgeStore
from src.llm.client import LLMClient
from src.llm.embedder import Embedder
from src.reasoning.prompt import ReasoningPromptBuilder

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GatheredContext:
    """The memory gathered for one question — retrieved chunks (what the
    project is now) and retrieved episodic entries (how it changed)."""

    chunks: list[Chunk]
    entries: list[EpisodicEntry]


class Reasoner:
    """Answers a question from Herald's standing memory — the read side of
    the two engines over the event stream: narration speaks on a change,
    this speaks on a question instead.

    The model-agnostic swap seam is the injected `LLMClient` — this class
    never constructs a concrete client, store, or embedder itself; a
    composition root wires the concretes in.
    """

    def __init__(
        self,
        llm: LLMClient,
        embedder: Embedder,
        knowledge: KnowledgeStore,
        episodic: EpisodicStore,
        reasoner_k: int = 8,
        prompt: ReasoningPromptBuilder | None = None,
    ) -> None:
        self._llm = llm
        self._embedder = embedder
        self._knowledge = knowledge
        self._episodic = episodic
        self._k = reasoner_k
        self._prompt = prompt if prompt is not None else ReasoningPromptBuilder()

    async def _gather_context(self, query: str, repo: str | None) -> GatheredContext:
        """Embed `query` once and query both memories with that same
        embedding, tolerating either store failing independently — a failed
        store contributes an empty result rather than aborting the answer."""
        embedding = (await self._embedder.embed([query]))[0]

        try:
            chunks = await self._knowledge.query(embedding, self._k, repo=repo)
        except Exception:
            logger.warning("knowledge store query failed, treating as empty", exc_info=True)
            chunks = []

        try:
            entries = await self._episodic.query(embedding, self._k, repo=repo)
        except Exception:
            logger.warning("episodic store query failed, treating as empty", exc_info=True)
            entries = []

        return GatheredContext(chunks=chunks, entries=entries)

    async def answer(self, query: str, repo: str | None = None) -> str:
        """Answer `query`, optionally scoped to `repo`.

        Gathers both memories through `_gather_context`, renders a reasoning
        prompt from whatever was retrieved, and always calls
        `LLMClient.generate` — when both memories are empty, the prompt
        builder emits an explicit no-memory framing instead of a grounded
        one, so the LLM answers honestly rather than fabricating.
        """
        gathered = await self._gather_context(query, repo)
        prompt = self._prompt.build(query, gathered.chunks, gathered.entries)
        return await self._llm.generate(prompt)
