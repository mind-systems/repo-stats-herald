"""End-to-end `EpisodicBackfill` + `PgEpisodicStore` round-trip.

Only meaningful against a real store: the in-memory idempotency test in
`test_backfill.py` cannot catch store-layer duplication, and the windowed
query only proves the historical-timestamp fix end-to-end when read back
through a real `since`/`until` filter rather than an in-memory list.
"""

from datetime import datetime, timezone
from pathlib import Path

from src.commits.collector import GitCommitCollector
from src.episodic.backfill import EpisodicBackfill
from src.episodic.linked_change import LinkedChangeResolver
from src.episodic.store import PgEpisodicStore
from src.knowledge.code_distiller import CodeDistiller
from src.knowledge.code_source_strategy import CodeSourceStrategy
from src.knowledge.source_strategy import AiFactorySourceStrategy
from src.llm.client import LLMClient
from src.llm.embedder import Embedder

REPO_NAME = "acme/widgets"
ORG_ID = 424242
EMBEDDING_DIM = 768


class _FakeMirror:
    def __init__(self, repo_path: Path, default_branch_name: str = "trunk") -> None:
        self._repo_path = repo_path
        self._default_branch_name = default_branch_name

    def ensure(self, repo: str, org_id: int) -> None:
        pass

    def object_store_path(self, repo: str) -> Path:
        return self._repo_path

    def default_branch(self, repo: str) -> str:
        return self._default_branch_name

    def tree(self, *args, **kwargs):
        raise AssertionError("EpisodicBackfill must never request a worktree for a historical step")


class _FakeEmbedder(Embedder):
    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * EMBEDDING_DIM]


class _FakeLLMClient(LLMClient):
    async def generate(self, prompt: str) -> str:
        return "a distilled description"


def _make_backfill(git_repo: Path, store: PgEpisodicStore) -> EpisodicBackfill:
    collector = GitCommitCollector()
    source_strategy = AiFactorySourceStrategy()
    return EpisodicBackfill(
        mirror=_FakeMirror(git_repo),
        resolver=LinkedChangeResolver(collector, source_strategy),
        embedder=_FakeEmbedder(),
        store=store,
        collector=collector,
        canonical_refs={},
        distiller=CodeDistiller(_FakeLLMClient()),
        code_strategy=CodeSourceStrategy(),
        source_strategy=source_strategy,
    )


async def test_query_returns_only_entries_inside_the_window(git_repo, commit_snapshot, store: PgEpisodicStore):
    commit_snapshot(git_repo, "old commit", write={"src/mod/a.py": "a = 1\n"}, when="2015-01-01T00:00:00+00:00")
    commit_snapshot(
        git_repo, "in window commit", write={"src/mod/b.py": "b = 1\n"}, when="2020-06-01T00:00:00+00:00"
    )
    commit_snapshot(
        git_repo, "future commit", write={"src/mod/c.py": "c = 1\n"}, when="2025-01-01T00:00:00+00:00"
    )

    backfill = _make_backfill(git_repo, store)
    await backfill.run(REPO_NAME, ORG_ID)

    results = await store.query(
        [0.0] * EMBEDDING_DIM,
        k=10,
        repo=REPO_NAME,
        since=datetime(2018, 1, 1, tzinfo=timezone.utc),
        until=datetime(2022, 1, 1, tzinfo=timezone.utc),
    )

    assert len(results) == 1
    assert results[0].changed_at == datetime.fromisoformat("2020-06-01T00:00:00+00:00")


async def test_two_runs_do_not_create_duplicate_rows(git_repo, commit_snapshot, store: PgEpisodicStore):
    commit_snapshot(git_repo, "commit 1", write={"src/mod/a.py": "a = 1\n"})
    commit_snapshot(git_repo, "commit 2", write={"src/mod/b.py": "b = 1\n"})

    backfill = _make_backfill(git_repo, store)
    await backfill.run(REPO_NAME, ORG_ID)
    await backfill.run(REPO_NAME, ORG_ID)

    results = await store.query([0.0] * EMBEDDING_DIM, k=100, repo=REPO_NAME)
    assert len(results) == 2
