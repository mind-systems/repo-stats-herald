import logging
from dataclasses import dataclass, field

from src.episodic.linked_change import LinkedChange
from src.episodic.models import EpisodicEntry
from src.episodic.store import EpisodicStore
from src.graph.store import ProjectGraph
from src.knowledge.store import Chunk, KnowledgeStore
from src.llm.client import LLMClient
from src.llm.embedder import Embedder
from src.reasoning.narration_prompt import NarrationPromptBuilder
from src.reasoning.prompt import ReasoningPromptBuilder

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GatheredContext:
    """The memory gathered for one question — retrieved chunks (what the
    project is now), retrieved episodic entries (how it changed), and
    semantic chunks from related neighbor projects (what the queried
    project relates to / unblocks — semantic only, no neighbor episodic
    entries)."""

    chunks: list[Chunk]
    entries: list[EpisodicEntry]
    neighbor_chunks: list[Chunk] = field(default_factory=list)


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
        graph: ProjectGraph,
        reasoner_k: int = 8,
        prompt: ReasoningPromptBuilder | None = None,
        narration_prompt: NarrationPromptBuilder | None = None,
    ) -> None:
        self._llm = llm
        self._embedder = embedder
        self._knowledge = knowledge
        self._episodic = episodic
        self._graph = graph
        self._k = reasoner_k
        self._prompt = prompt if prompt is not None else ReasoningPromptBuilder()
        self._narration_prompt = narration_prompt if narration_prompt is not None else NarrationPromptBuilder()

    async def _gather_context(self, query: str, repo: str | None) -> GatheredContext:
        """Embed `query` once and query both memories with that same
        embedding, tolerating either store failing independently — a failed
        store contributes an empty result rather than aborting the answer.

        When `repo` is scoped, also folds in semantic context from related
        neighbor projects — discovered via org-wide retrieval unioned with
        the directed project graph — reusing the same embedding and `k`,
        with each discovery/query step isolated so one neighbor's or one
        discovery method's failure never drops the primary context or the
        other neighbors."""
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

        neighbor_chunks: list[Chunk] = []
        if repo is not None:
            neighbor_ids: list[str] = []
            seen_neighbors: set[str] = set()

            try:
                retrieval_hits = await self._knowledge.query(embedding, self._k, repo=None)
            except Exception:
                logger.warning("org-wide neighbor discovery failed, treating as empty", exc_info=True)
                retrieval_hits = []

            for hit in retrieval_hits:
                if hit.repo is None or hit.repo == repo or hit.repo in seen_neighbors:
                    continue
                seen_neighbors.add(hit.repo)
                neighbor_ids.append(hit.repo)

            try:
                graph_neighbors = await self._graph.neighbors(repo)
            except Exception:
                logger.warning("project graph neighbor lookup failed, treating as empty", exc_info=True)
                graph_neighbors = []

            for neighbor in graph_neighbors:
                if neighbor == repo or neighbor in seen_neighbors:
                    continue
                seen_neighbors.add(neighbor)
                neighbor_ids.append(neighbor)

            for neighbor in neighbor_ids:
                try:
                    neighbor_chunks.extend(await self._knowledge.query(embedding, self._k, repo=neighbor))
                except Exception:
                    logger.warning(
                        "neighbor %s knowledge query failed, dropping this neighbor", neighbor, exc_info=True
                    )

        return GatheredContext(chunks=chunks, entries=entries, neighbor_chunks=neighbor_chunks)

    async def answer(self, query: str, repo: str | None = None) -> str:
        """Answer `query`, optionally scoped to `repo`.

        Gathers both memories through `_gather_context`, renders a reasoning
        prompt from whatever was retrieved, and always calls
        `LLMClient.generate` — when both memories are empty, the prompt
        builder emits an explicit no-memory framing instead of a grounded
        one, so the LLM answers honestly rather than fabricating.
        """
        gathered = await self._gather_context(query, repo)
        prompt = self._prompt.build(query, gathered.chunks, gathered.entries, gathered.neighbor_chunks)
        return await self._llm.generate(prompt)

    async def narrate(self, change: LinkedChange, lang: str = "ru") -> str:
        """Narrate `change` at feature level, in `lang`.

        Reuses `_gather_context` (the same retrieval+neighbor step `answer`
        calls) scoped to `change.repo`, then renders a narration prompt —
        completed tasks lead, commits are supporting detail, cross-project
        neighbors are framed as what the change "unblocks" — instead of
        `answer`'s Q&A prompt. `change.commits` always populates the
        retrieval query and the prompt, so this never returns empty: when
        retrieval/neighbor context is unavailable, the note degrades to a
        commits-only digest rather than failing.
        """
        query = self._narration_query(change)
        gathered = await self._gather_context(query, change.repo)
        prompt = self._narration_prompt.build(
            change, gathered.chunks, gathered.entries, gathered.neighbor_chunks, lang
        )
        return await self._llm.generate(prompt)

    def _narration_query(self, change: LinkedChange) -> str:
        """Build the retrieval query from both completed tasks and commit
        messages — neither source is dropped when the other is empty."""
        parts = list(change.completed_tasks)
        parts.extend(commit.message for commit in change.commits.commits)
        return "\n".join(parts)
