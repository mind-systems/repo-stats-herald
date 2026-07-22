from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from src.core.config import get_settings
from src.core.db import create_pool
from src.ingestion.router import router as ingestion_router
from src.ingestion.served_repos import ServedRepoStore

SCHEMA_PATH = Path(__file__).resolve().parent / "ingestion" / "schema.sql"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    pool = await create_pool(settings.postgres_dsn)
    async with pool.acquire() as conn:
        await conn.execute(SCHEMA_PATH.read_text())
    app.state.served_repo_store = ServedRepoStore(pool)

    yield

    await pool.close()


app = FastAPI(title="repo-stats-herald", lifespan=lifespan)
app.include_router(ingestion_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
