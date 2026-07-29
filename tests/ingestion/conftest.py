import contextlib
import os
from collections.abc import AsyncGenerator, Iterator
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import asyncpg
import pytest

from src.commits.models import Commit, CommitContext
from src.core.db import create_pool
from src.episodic.linked_change import LinkedChange
from src.episodic.models import EpisodicEntry
from src.episodic.store import EpisodicStore
from src.ingestion.models import PushCommit, PushEvent
from src.ingestion.served_repos import ServedRepoStore
from src.ingestion.writer import EpisodicWriter
from src.llm.embedder import Embedder

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "src" / "ingestion" / "schema.sql"


def _dsn() -> str:
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5432")
    user = quote(os.environ.get("POSTGRES_USER", "herald_username"), safe="")
    password = quote(os.environ.get("POSTGRES_PASSWORD", "herald_password"), safe="")
    db = os.environ.get("POSTGRES_DB", "herald_database")
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"

# --- Fakes -------------------------------------------------------------
#
# `EpisodicWriter(mirror, resolver, embedder, store, collector)` — the
# collector is last, after the store. Getting this order wrong in a fixture
# produces confusing `AttributeError`s rather than a clean failure.


class FakeMirror:
    """Fake `RepoMirror`. `tree()` is a **synchronous** context manager (the
    real `RepoMirror.tree` is sync today; roadmap 20.2.2 will make it
    awaitable, but these fakes and the assertions built on them are meant to
    survive that unchanged). `ensure`/`tree_enter`/`tree_exit` are appended to
    a shared ordered `events` log also written to by `FakeEmbedder` and
    `FakeStore`, so a single test can assert orchestration order across the
    whole `write()` call.
    """

    def __init__(self, tree_path: Path, events: list[str]) -> None:
        self.tree_path = tree_path
        self.events = events
        self.ensure_calls: list[tuple[str, int]] = []
        self.tree_calls: list[tuple[str, int, str]] = []

    def ensure(self, repo: str, org_id: int) -> None:
        self.ensure_calls.append((repo, org_id))
        self.events.append("ensure")

    @contextlib.contextmanager
    def tree(self, repo: str, org_id: int, ref: str) -> Iterator[Path]:
        self.tree_calls.append((repo, org_id, ref))
        self.events.append("tree_enter")
        try:
            yield self.tree_path
        finally:
            self.events.append("tree_exit")


class FakeResolver:
    """Fake `LinkedChangeResolver`. Returns a canned `LinkedChange` and
    records the exact args it was called with, so a test can assert both
    what the writer passed in and what came back out."""

    def __init__(self, change: LinkedChange) -> None:
        self.change = change
        self.calls: list[tuple[str, str, str]] = []

    def resolve(self, repo_path: str, before: str, after: str) -> LinkedChange:
        self.calls.append((repo_path, before, after))
        return self.change


class FakeCollector:
    """Fake `GitCommitCollector`. Only `commit_timestamp` is used by the
    writer. Backed by a `dict[ref -> datetime]` so a writer that asks for the
    wrong ref (`push.before` instead of `push.after`) gets a different,
    detectable value rather than silently matching."""

    def __init__(self, timestamps: dict[str, datetime]) -> None:
        self.timestamps = timestamps
        self.calls: list[tuple[str, str]] = []

    def commit_timestamp(self, repo_path: str, ref: str) -> datetime:
        self.calls.append((repo_path, ref))
        return self.timestamps[ref]


class FailingCollector:
    """Fake `GitCommitCollector` whose `commit_timestamp` always raises —
    used to pin that the writer propagates rather than falling back to
    `datetime.now()`."""

    def __init__(self, error: Exception) -> None:
        self._error = error

    def commit_timestamp(self, repo_path: str, ref: str) -> datetime:
        raise self._error


class FakeEmbedder(Embedder):
    """Fake `Embedder`. Records every `embed()` call's input texts and
    returns one canned vector per input. Appends to the shared `events` log
    so embed-vs-worktree-close and embed-vs-append ordering is assertable."""

    def __init__(self, events: list[str], vector: list[float] | None = None) -> None:
        self.events = events
        self.calls: list[list[str]] = []
        self.vector = vector if vector is not None else [0.1] * 768

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        self.events.append("embed")
        return [self.vector]


class FailingEmbedder(Embedder):
    """Fake `Embedder` whose `embed()` always raises — used to pin that a
    failed embed leaves nothing appended."""

    def __init__(self, error: Exception) -> None:
        self._error = error

    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise self._error


class FakeStore(EpisodicStore):
    """Fake `EpisodicStore`. `append` collects entries and appends to the
    shared `events` log; `query` and `recorded_commit_shas` raise, which
    doubles as the "never reads at write time" assertion. Deliberately has no
    update/delete method — adding one would make the append-only assertions
    vacuous."""

    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.entries: list[EpisodicEntry] = []

    async def append(self, entry: EpisodicEntry) -> None:
        self.entries.append(entry)
        self.events.append("append")

    async def query(
        self,
        embedding: list[float],
        k: int,
        repo: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[EpisodicEntry]:
        raise AssertionError("FakeStore.query must not be called while writing")

    async def recorded_commit_shas(self, repo: str) -> set[str]:
        raise AssertionError("FakeStore.recorded_commit_shas must not be called while writing")


class FailingStore(EpisodicStore):
    """Fake `EpisodicStore` whose `append` always raises — used to pin that
    an append failure propagates rather than being swallowed."""

    def __init__(self, error: Exception) -> None:
        self._error = error

    async def append(self, entry: EpisodicEntry) -> None:
        raise self._error

    async def query(self, *args, **kwargs) -> list[EpisodicEntry]:
        raise AssertionError("FakeStore.query must not be called while writing")

    async def recorded_commit_shas(self, repo: str) -> set[str]:
        raise AssertionError("FakeStore.recorded_commit_shas must not be called while writing")


# --- Fixtures ------------------------------------------------------------


@pytest.fixture
def events() -> list[str]:
    return []


@pytest.fixture
def mirror(tmp_path: Path, events: list[str]) -> FakeMirror:
    return FakeMirror(tmp_path, events)


@pytest.fixture
def embedder(events: list[str]) -> FakeEmbedder:
    return FakeEmbedder(events)


@pytest.fixture
def store(events: list[str]) -> FakeStore:
    return FakeStore(events)


@pytest.fixture
def make_push():
    def _make_push(
        org_id: int = 424242,
        org_login: str = "acme-org",
        repo: str = "acme/widgets",
        branch: str = "main",
        before: str = "before-sha",
        after: str = "after-sha",
        commits: tuple[PushCommit, ...] | None = None,
    ) -> PushEvent:
        if commits is None:
            commits = (
                PushCommit(
                    sha="zzz-payload-sha",
                    message="payload message (never read by the writer)",
                    added=("payload-added.txt",),
                    modified=(),
                    removed=(),
                    author="Payload Author",
                ),
            )
        return PushEvent(
            org_id=org_id,
            org_login=org_login,
            repo=repo,
            branch=branch,
            before=before,
            after=after,
            commits=commits,
        )

    return _make_push


@pytest.fixture
def make_commit():
    def _make_commit(
        sha: str = "aaa",
        author: str = "Resolved Author",
        message: str = "resolved commit message",
        changed_files: tuple[str, ...] = (),
        diffstat: str = "",
    ) -> Commit:
        return Commit(
            sha=sha,
            author=author,
            message=message,
            changed_files=changed_files,
            diffstat=diffstat,
        )

    return _make_commit


@pytest.fixture
def make_change():
    def _make_change(
        repo: str = "acme/widgets",
        branch: str = "main",
        completed_tasks: tuple[str, ...] = (),
        commits: tuple[Commit, ...] = (),
    ) -> LinkedChange:
        return LinkedChange(
            repo=repo,
            completed_tasks=completed_tasks,
            commits=CommitContext(repo=repo, branch=branch, commits=commits),
        )

    return _make_change


@pytest.fixture
def make_resolver():
    def _make_resolver(change: LinkedChange) -> FakeResolver:
        return FakeResolver(change)

    return _make_resolver


@pytest.fixture
def make_collector():
    def _make_collector(timestamps: dict[str, datetime]) -> FakeCollector:
        return FakeCollector(timestamps)

    return _make_collector


@pytest.fixture
def make_writer(mirror: FakeMirror, embedder: FakeEmbedder, store: FakeStore):
    def _make_writer(resolver, collector, mirror=mirror, embedder=embedder, store=store) -> EpisodicWriter:
        return EpisodicWriter(mirror, resolver, embedder, store, collector)

    return _make_writer


@pytest.fixture
async def pg_pool() -> AsyncGenerator[asyncpg.Pool, None]:
    pool = await create_pool(_dsn())
    schema = SCHEMA_PATH.read_text()
    async with pool.acquire() as conn:
        await conn.execute(schema)
        await conn.execute("TRUNCATE served_repos")
    yield pool
    await pool.close()


@pytest.fixture
def served_store(pg_pool: asyncpg.Pool) -> ServedRepoStore:
    return ServedRepoStore(pg_pool)
