from src.episodic.store import EpisodicStore
from src.knowledge.store import KnowledgeStore
from src.llm.client import LLMClient
from src.llm.embedder import Embedder


class Reasoner:
    """Answers a question from Herald's standing memory — the read side of
    the two engines over the event stream: narration speaks on a change,
    this speaks on a question instead.

    The model-agnostic swap seam is the injected `LLMClient` — this class
    never constructs a concrete client, store, or embedder itself; a future
    composition root wires the concretes in.
    """

    def __init__(
        self,
        llm: LLMClient,
        embedder: Embedder,
        knowledge: KnowledgeStore,
        episodic: EpisodicStore,
    ) -> None:
        self._llm = llm
        self._embedder = embedder
        self._knowledge = knowledge
        self._episodic = episodic

    async def answer(self, query: str, repo: str | None = None) -> str:
        """Answer `query`, optionally scoped to `repo`.

        Intended shape (not yet implemented — this stub always raises):

        - Embed `query` exactly once via `embed([query])[0]` and reuse that
          one embedding for both retrieval calls below — never re-embed per
          store.
        - Query `KnowledgeStore.query(embedding, k, repo=repo)` and
          `EpisodicStore.query(embedding, k, repo=repo)` with that same
          embedding. `since`/`until` stay at their `None` defaults on the
          episodic call — no time window. `repo` is passed through exactly
          as given: the bare `push.repo` name (never `org/repo`) when
          scoping to one project, `None` for an org-wide question — never
          silently defaulted either way. The exact `k` is not fixed by this
          contract.
        - Assemble the combined context from whatever each store returned,
          tolerating either store failing independently: a failure in one
          store must not prevent an answer grounded in the survivor, and a
          failure in both falls back to the honest no-memory path below.
        - Where both stores return nothing, say so rather than inventing an
          answer — either by short-circuiting before any `LLMClient.generate`
          call, or by building a prompt that carries an explicit no-memory
          marker distinguishing it from a prompt built from real context.
        - Build a reasoning prompt from the combined context and call
          `LLMClient.generate(prompt)` for the final answer.
        """
        raise NotImplementedError
