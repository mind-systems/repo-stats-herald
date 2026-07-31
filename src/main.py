import functools
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from src.changelog.release import release_report
from src.commits.collector import GitCommitCollector
from src.core.config import get_settings
from src.core.db import create_pool
from src.delivery.changelog_client import ChangelogClient
from src.delivery.github_release import GitHubReleaseClient
from src.delivery.service import DeliveryService, ReleaseDelivery
from src.delivery.telegram import TelegramClient
from src.episodic.linked_change import LinkedChangeResolver
from src.episodic.store import PgEpisodicStore
from src.github.app_auth import GitHubAppAuth
from src.github.mirror import RepoMirror
from src.graph.coordination import CoordinationSeeder
from src.graph.models import Edge, EdgeKind
from src.graph.store import PgProjectGraph
from src.ingestion.router import router as ingestion_router
from src.ingestion.served_repos import ServedRepoStore
from src.ingestion.writer import EpisodicWriter
from src.knowledge.indexer import ArtifactIndexer
from src.knowledge.source_strategy import AiFactorySourceStrategy
from src.knowledge.store import PgVectorStore
from src.knowledge.sync import KnowledgeSync
from src.llm.client import OllamaClient
from src.llm.embedder import OllamaEmbedder
from src.reasoning.localizer import PivotLocalizer
from src.reasoning.reasoner import Reasoner
from src.reasoning.translator import LLMTranslator
from src.routing.resolver import DeliveryPlanResolver
from src.versioning.versioner import Versioner

SCHEMA_PATH = Path(__file__).resolve().parent / "ingestion" / "schema.sql"
KNOWLEDGE_SCHEMA_PATH = Path(__file__).resolve().parent / "knowledge" / "schema.sql"
EPISODIC_SCHEMA_PATH = Path(__file__).resolve().parent / "episodic" / "schema.sql"
GRAPH_SCHEMA_PATH = Path(__file__).resolve().parent / "graph" / "schema.sql"

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    pool = await create_pool(settings.postgres_dsn)
    async with pool.acquire() as conn:
        await conn.execute(SCHEMA_PATH.read_text())
        await conn.execute(KNOWLEDGE_SCHEMA_PATH.read_text())
        await conn.execute(EPISODIC_SCHEMA_PATH.read_text())
        await conn.execute(GRAPH_SCHEMA_PATH.read_text())
    app.state.served_repo_store = ServedRepoStore(pool)

    graph = PgProjectGraph(pool)
    app.state.project_graph = graph
    for from_repo, to_repo, kind in settings.project_edges:
        await graph.add_edge(
            Edge(from_repo=from_repo, to_repo=to_repo, kind=EdgeKind(kind), source="config")
        )
    logger.info("loaded %d config project edges", len(settings.project_edges))

    app.state.delivery_plan_resolver = DeliveryPlanResolver(settings)

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
        await mirror.sweep_worktrees()

        seeder = CoordinationSeeder(mirror, graph, settings.canonical_refs)
        app.state.knowledge_sync = KnowledgeSync(
            mirror, indexer, strategy, settings.canonical_refs, seeder
        )

        episodic_store = PgEpisodicStore(pool)
        collector = GitCommitCollector()
        resolver = LinkedChangeResolver(collector, strategy)
        app.state.episodic_writer = EpisodicWriter(mirror, resolver, embedder, episodic_store, collector)

        app.state.mirror = mirror
        llm = OllamaClient(settings.ollama_url, settings.ollama_model, settings.ollama_api_key)
        reasoner = Reasoner(
            llm=llm,
            embedder=embedder,
            knowledge=store,
            episodic=episodic_store,
            graph=graph,
            reasoner_k=settings.reasoner_k,
        )
        app.state.localizer = PivotLocalizer(reasoner, LLMTranslator(llm), pivot=settings.pivot_lang)
        app.state.versioner = Versioner(mirror, collector, settings.version_increment)
        app.state.github_release_client = GitHubReleaseClient(auth)
        app.state.delivery_service = DeliveryService(TelegramClient(settings.telegram_bot_token))
        app.state.changelog_client = ChangelogClient()
        app.state.build_release_report = functools.partial(
            release_report, mirror=mirror, collector=collector, resolver=resolver, reasoner=reasoner
        )
        app.state.release_delivery = ReleaseDelivery(
            mirror=mirror,
            delivery_plan_resolver=app.state.delivery_plan_resolver,
            versioner=app.state.versioner,
            build_release_report=app.state.build_release_report,
            localizer=app.state.localizer,
            github_release_client=app.state.github_release_client,
            delivery_service=app.state.delivery_service,
            changelog_client=app.state.changelog_client,
        )
    else:
        logger.warning("canonical-ref sync disabled: GitHub App, mirror, or org-login settings absent")

    yield

    await pool.close()


app = FastAPI(title="repo-stats-herald", lifespan=lifespan)
app.include_router(ingestion_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
