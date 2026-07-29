import os
from collections.abc import AsyncGenerator, Callable
from pathlib import Path
from urllib.parse import quote

import asyncpg
import pytest

from src.core.db import create_pool
from src.graph.models import Edge, EdgeKind
from src.graph.store import PgProjectGraph

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "src" / "graph" / "schema.sql"


def _dsn() -> str:
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5432")
    user = quote(os.environ.get("POSTGRES_USER", "herald_username"), safe="")
    password = quote(os.environ.get("POSTGRES_PASSWORD", "herald_password"), safe="")
    db = os.environ.get("POSTGRES_DB", "herald_database")
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


@pytest.fixture
async def pg_pool() -> AsyncGenerator[asyncpg.Pool, None]:
    pool = await create_pool(_dsn())
    schema = SCHEMA_PATH.read_text()
    async with pool.acquire() as conn:
        await conn.execute(schema)
        await conn.execute("TRUNCATE project_edges")
    yield pool
    await pool.close()


@pytest.fixture
def store(pg_pool: asyncpg.Pool) -> PgProjectGraph:
    return PgProjectGraph(pg_pool)


@pytest.fixture
def make_edge() -> Callable[..., Edge]:
    def _make_edge(
        from_repo: str = "org/a",
        to_repo: str = "org/b",
        kind: EdgeKind = EdgeKind.CONTRACT,
        source: str = "config",
    ) -> Edge:
        return Edge(from_repo=from_repo, to_repo=to_repo, kind=kind, source=source)

    return _make_edge
