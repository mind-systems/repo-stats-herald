import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from src.core.config import get_settings
from src.core.db import create_pool
from src.github.app_auth import GitHubAppAuth
from src.github.mirror import RepoMirror
from src.ingestion.router import router as ingestion_router
from src.ingestion.served_repos import ServedRepoStore
from src.knowledge.indexer import ArtifactIndexer
from src.knowledge.source_strategy import AiFactorySourceStrategy
from src.knowledge.store import PgVectorStore
from src.knowledge.sync import KnowledgeSync
from src.llm.embedder import OllamaEmbedder

SCHEMA_PATH = Path(__file__).resolve().parent / "ingestion" / "schema.sql"
KNOWLEDGE_SCHEMA_PATH = Path(__file__).resolve().parent / "knowledge" / "schema.sql"

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    pool = await create_pool(settings.postgres_dsn)
    async with pool.acquire() as conn:
        await conn.execute(SCHEMA_PATH.read_text())
        await conn.execute(KNOWLEDGE_SCHEMA_PATH.read_text())
    app.state.served_repo_store = ServedRepoStore(pool)

    if (
        settings.github_app_id is not None
        and settings.github_app_private_key_path is not None
        and settings.mirror_root
        and settings.github_org_logins
    ):
        embedder = OllamaEmbedder(settings.ollama_url, settings.embed_model, settings.ollama_api_key)
        store = PgVectorStore(pool)
        strategy = AiFactorySourceStrategy()
        indexer = ArtifactIndexer(strategy, embedder, store)

        pem = Path(settings.github_app_private_key_path).read_text()
        auth = GitHubAppAuth(settings.github_app_id, pem)

        def clone_source(repo: str, org_id: int) -> str:
            login = settings.github_org_logins.get(org_id)
            if login is None:
                raise LookupError(f"no GITHUB_ORG_LOGINS entry for org_id={org_id}")
            return f"https://github.com/{login}/{repo}.git"

        mirror = RepoMirror(Path(settings.mirror_root), auth, clone_source)
        mirror.sweep_worktrees()

        app.state.knowledge_sync = KnowledgeSync(mirror, indexer, strategy, settings.canonical_refs)
    else:
        logger.warning("canonical-ref sync disabled: GitHub App, mirror, or org-login settings absent")

    yield

    await pool.close()


app = FastAPI(title="repo-stats-herald", lifespan=lifespan)
app.include_router(ingestion_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
