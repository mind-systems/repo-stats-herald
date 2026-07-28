from datetime import datetime, timezone

import pytest

from src.episodic.models import EpisodicEntry
from src.episodic.store import EpisodicStore
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
    preset `result` or raises the preset `error`, whichever is set."""

    def __init__(self) -> None:
        self.calls: list[tuple[list[float], int, str | None]] = []
        self.result: list[Chunk] = []
        self.error: Exception | None = None

    async def upsert(self, repo: str, path: str, items: list[Chunk]) -> None:
        pass

    async def delete(self, repo: str, path: str) -> None:
        pass

    async def query(self, embedding: list[float], k: int, repo: str | None = None) -> list[Chunk]:
        self.calls.append((embedding, k, repo))
        if self.error is not None:
            raise self.error
        return self.result


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
def reasoner(
    fake_llm: FakeLLMClient,
    fake_embedder: FakeEmbedder,
    fake_knowledge: FakeKnowledgeStore,
    fake_episodic: FakeEpisodicStore,
) -> Reasoner:
    return Reasoner(llm=fake_llm, embedder=fake_embedder, knowledge=fake_knowledge, episodic=fake_episodic)


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
