import os
from collections.abc import AsyncGenerator, Callable
from datetime import datetime, timezone
from pathlib import Path

import asyncpg
import pytest

from src.core.db import create_pool
from src.episodic.models import EpisodicEntry
from src.episodic.store import PgEpisodicStore

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "src" / "episodic" / "schema.sql"

EMBEDDING_DIM = 768


def _dsn() -> str:
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5432")
    user = os.environ.get("POSTGRES_USER", "herald_username")
    password = os.environ.get("POSTGRES_PASSWORD", "herald_password")
    db = os.environ.get("POSTGRES_DB", "herald_database")
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


@pytest.fixture
async def pg_pool() -> AsyncGenerator[asyncpg.Pool, None]:
    pool = await create_pool(_dsn())
    schema = SCHEMA_PATH.read_text()
    async with pool.acquire() as conn:
        await conn.execute(schema)
        await conn.execute("TRUNCATE episodic_entries")
    yield pool
    await pool.close()


@pytest.fixture
def store(pg_pool: asyncpg.Pool) -> PgEpisodicStore:
    return PgEpisodicStore(pg_pool)


@pytest.fixture
def make_entry() -> Callable[..., EpisodicEntry]:
    def _make_entry(
        content: str,
        axis: int,
        value: float = 1.0,
        repo: str = "org/repo",
        org_id: int = 1,
        completed_tasks: tuple[str, ...] = ("task-1",),
        commit_shas: tuple[str, ...] = ("abc123",),
        changed_at: datetime = datetime(2024, 1, 1, tzinfo=timezone.utc),
    ) -> EpisodicEntry:
        embedding = [0.0] * EMBEDDING_DIM
        embedding[axis] = value
        return EpisodicEntry(
            repo=repo,
            org_id=org_id,
            completed_tasks=completed_tasks,
            commit_shas=commit_shas,
            content=content,
            embedding=embedding,
            changed_at=changed_at,
        )

    return _make_entry
