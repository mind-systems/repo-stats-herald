from datetime import datetime, timezone

import pytest

from src.episodic.models import EpisodicEntry
from src.episodic.store import EpisodicStore
from src.graph.models import Edge
from src.graph.store import ProjectGraph
from src.knowledge.store import Chunk, KnowledgeStore
from src.llm.client import LLMClient
from src.llm.embedder import Embedder
from src.reasoning.reasoner import Reasoner


class FakeEmbedder(Embedder):
    """Records every `embed` call and returns one fixed sentinel vector per
    input text — the same vector object every time, so tests can assert
    identity of "the same embedding" as it flows into both stores."""

    SENTINEL_VECTOR = [0.1, 0.2, 0.3]

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        return [self.SENTINEL_VECTOR for _ in texts]


class FakeKnowledgeStore(KnowledgeStore):
    """Configurable fake — `query` records its args and either returns the
    preset `result` or raises the preset `error`, whichever is set.

    `results`/`errors` give per-`repo` control (keyed by the `repo` argument,
    including `None` for org-wide discovery), consulted first and falling
    back to the single `result`/`error` when a key is absent — so contract
    tests that only ever set the single fields keep working unchanged."""

    def __init__(self) -> None:
        self.calls: list[tuple[list[float], int, str | None]] = []
        self.result: list[Chunk] = []
        self.error: Exception | None = None
        self.results: dict[str | None, list[Chunk]] = {}
        self.errors: dict[str | None, Exception] = {}

    async def upsert(self, repo: str, path: str, items: list[Chunk]) -> None:
        pass

    async def delete(self, repo: str, path: str) -> None:
        pass

    async def query(self, embedding: list[float], k: int, repo: str | None = None) -> list[Chunk]:
        self.calls.append((embedding, k, repo))
        error = self.errors.get(repo, self.error)
        if error is not None:
            raise error
        return self.results.get(repo, self.result)


class FakeEpisodicStore(EpisodicStore):
    """Configurable fake — `query` records its args and either returns the
    preset `result` or raises the preset `error`, whichever is set."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.result: list[EpisodicEntry] = []
        self.error: Exception | None = None

    async def append(self, entry: EpisodicEntry) -> None:
        pass

    async def query(
        self,
        embedding: list[float],
        k: int,
        repo: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[EpisodicEntry]:
        self.calls.append((embedding, k, repo, since, until))
        if self.error is not None:
            raise self.error
        return self.result

    async def recorded_commit_shas(self, repo: str) -> set[str]:
        return set()


class FakeProjectGraph(ProjectGraph):
    """Configurable fake — `neighbors` records its calls and either returns
    the preset `result` (defaulting to an empty list when unconfigured) or
    raises the preset `error`. The other four `ProjectGraph` abstractmethods
    are stubbed trivially since this fake only exercises `neighbors`."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.result: list[str] = []
        self.error: Exception | None = None

    async def add_edge(self, edge: Edge) -> None:
        pass

    async def edges_from(self, repo: str) -> list[Edge]:
        return []

    async def neighbors(self, repo: str) -> list[str]:
        self.calls.append(repo)
        if self.error is not None:
            raise self.error
        return self.result

    async def remove_seed_edges(self, from_repo: str) -> None:
        pass

    async def replace_seed_edges(self, from_repo: str, edges: list[Edge]) -> None:
        pass


class FakeLLMClient(LLMClient):
    """Records every prompt it is given and returns a deterministic
    per-call marker."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def generate(self, prompt: str) -> str:
        self.calls.append(prompt)
        return f"answer:{len(self.calls)}"


@pytest.fixture
def fake_embedder() -> FakeEmbedder:
    return FakeEmbedder()


@pytest.fixture
def fake_llm() -> FakeLLMClient:
    return FakeLLMClient()


@pytest.fixture
def fake_knowledge() -> FakeKnowledgeStore:
    return FakeKnowledgeStore()


@pytest.fixture
def fake_episodic() -> FakeEpisodicStore:
    return FakeEpisodicStore()


@pytest.fixture
def fake_graph() -> FakeProjectGraph:
    return FakeProjectGraph()


@pytest.fixture
def reasoner(
    fake_llm: FakeLLMClient,
    fake_embedder: FakeEmbedder,
    fake_knowledge: FakeKnowledgeStore,
    fake_episodic: FakeEpisodicStore,
    fake_graph: FakeProjectGraph,
) -> Reasoner:
    return Reasoner(
        llm=fake_llm,
        embedder=fake_embedder,
        knowledge=fake_knowledge,
        episodic=fake_episodic,
        graph=fake_graph,
    )


@pytest.fixture
def make_chunk():
    def _make_chunk(
        content: str = "chunk content",
        repo: str | None = "api",
        path: str | None = "src/thing.py",
        chunk_index: int | None = 0,
    ) -> Chunk:
        return Chunk(
            content=content,
            embedding=FakeEmbedder.SENTINEL_VECTOR,
            repo=repo,
            path=path,
            chunk_index=chunk_index,
        )

    return _make_chunk


@pytest.fixture
def make_entry():
    def _make_entry(
        content: str = "entry content",
        repo: str = "api",
        org_id: int = 1,
        completed_tasks: tuple[str, ...] = ("task-1",),
        commit_shas: tuple[str, ...] = ("abc123",),
        changed_at: datetime | None = None,
    ) -> EpisodicEntry:
        return EpisodicEntry(
            repo=repo,
            org_id=org_id,
            completed_tasks=completed_tasks,
            commit_shas=commit_shas,
            content=content,
            embedding=FakeEmbedder.SENTINEL_VECTOR,
            changed_at=changed_at or datetime(2024, 1, 1, tzinfo=timezone.utc),
        )

    return _make_entry
