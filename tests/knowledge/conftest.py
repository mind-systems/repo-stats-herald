import os
from collections.abc import AsyncGenerator, Callable
from pathlib import Path

import asyncpg
import pytest

from src.core.db import create_pool
from src.knowledge.store import Chunk, PgVectorStore

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "src" / "knowledge" / "schema.sql"

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
        await conn.execute("TRUNCATE chunks")
    yield pool
    await pool.close()


@pytest.fixture
def store(pg_pool: asyncpg.Pool) -> PgVectorStore:
    return PgVectorStore(pg_pool)


@pytest.fixture
def make_chunk() -> Callable[..., Chunk]:
    def _make_chunk(content: str, axis: int, value: float = 1.0) -> Chunk:
        embedding = [0.0] * EMBEDDING_DIM
        embedding[axis] = value
        return Chunk(content=content, embedding=embedding)

    return _make_chunk
