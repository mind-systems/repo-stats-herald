"""Composition root: build a named schedule's report for every served repo
and deliver it to that org's Telegram channel.

Run as a module from the project root:

    uv run python -m scripts.report --schedule <name>
"""

import argparse
import asyncio
import logging
from pathlib import Path

from src.changelog.report import report_for_schedule, schedule_by_name
from src.changelog.sections import default_section_registry
from src.commits.collector import GitCommitCollector
from src.core.config import get_settings
from src.core.db import create_pool
from src.delivery.service import DeliveryService
from src.delivery.telegram import TelegramClient
from src.episodic.linked_change import LinkedChangeResolver
from src.episodic.store import PgEpisodicStore
from src.github.app_auth import GitHubAppAuth
from src.github.mirror import RepoMirror, resolve_canonical_ref
from src.graph.store import PgProjectGraph
from src.ingestion.served_repos import ServedRepoStore
from src.knowledge.source_strategy import AiFactorySourceStrategy
from src.knowledge.store import PgVectorStore
from src.llm.client import OllamaClient
from src.llm.embedder import OllamaEmbedder
from src.reasoning.reasoner import Reasoner
from src.reasoning.remaining_prompt import RemainingPromptBuilder
from src.routing.resolver import DeliveryPlanResolver

INGESTION_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "src" / "ingestion" / "schema.sql"
KNOWLEDGE_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "src" / "knowledge" / "schema.sql"
EPISODIC_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "src" / "episodic" / "schema.sql"
GRAPH_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "src" / "graph" / "schema.sql"

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a named schedule's report for every served repo and deliver it.",
    )
    parser.add_argument("--schedule", required=True, help="Report schedule name (see REPORT_SCHEDULES)")
    return parser.parse_args()


async def _run(schedule_name: str) -> None:
    settings = get_settings()
    pool = await create_pool(settings.postgres_dsn)
    try:
        async with pool.acquire() as conn:
            await conn.execute(INGESTION_SCHEMA_PATH.read_text())
            await conn.execute(KNOWLEDGE_SCHEMA_PATH.read_text())
            await conn.execute(EPISODIC_SCHEMA_PATH.read_text())
            await conn.execute(GRAPH_SCHEMA_PATH.read_text())

        llm = OllamaClient(settings.ollama_url, settings.ollama_model, settings.ollama_api_key)
        embedder = OllamaEmbedder(settings.ollama_url, settings.embed_model, settings.ollama_api_key)
        reasoner = Reasoner(
            llm=llm,
            embedder=embedder,
            knowledge=PgVectorStore(pool),
            episodic=PgEpisodicStore(pool),
            graph=PgProjectGraph(pool),
            reasoner_k=settings.reasoner_k,
        )

        collector = GitCommitCollector()
        strategy = AiFactorySourceStrategy()
        resolver = LinkedChangeResolver(collector, strategy)
        remaining_prompt = RemainingPromptBuilder()

        pem = Path(settings.github_app_private_key_path).read_text()
        auth = GitHubAppAuth(settings.github_app_id, pem)

        def clone_source(repo: str, org_id: int) -> str:
            login = settings.github_org_logins.get(org_id)
            if login is None:
                raise LookupError(f"no GITHUB_ORG_LOGINS entry for org_id={org_id}")
            return f"https://github.com/{login}/{repo}.git"

        mirror = RepoMirror(Path(settings.mirror_root), auth, clone_source)
        mirror.sweep_worktrees()

        registry = default_section_registry(
            mirror, resolver, reasoner, collector, strategy, llm, remaining_prompt
        )

        schedule = schedule_by_name(settings.report_schedules, schedule_name)
        report = report_for_schedule(
            schedule,
            registry,
            mirror=mirror,
            collector=collector,
            canonical_refs=settings.canonical_refs,
        )

        plan_resolver = DeliveryPlanResolver(settings)
        delivery = DeliveryService(TelegramClient(settings.telegram_bot_token))
        served = ServedRepoStore(pool)

        delivered = 0
        skipped_empty = 0
        skipped_no_channel = 0
        failed = 0

        for org_id, repo in await served.all():
            try:
                # The cron is decoupled from the push path, so it always
                # ensures before building rather than assuming a push
                # already did.
                mirror.ensure(repo, org_id)

                # Passed as the `branch` arg purely to avoid a fake branch —
                # the report path consumes only `plan.telegram_channel` and
                # `plan.language`, never `plan.branch_role`/`is_release`/
                # `is_prerelease`.
                canonical = resolve_canonical_ref(repo, settings.canonical_refs, mirror)
                plan = plan_resolver.resolve(org_id, repo, canonical)

                text = await report.build(repo, org_id, lang=plan.language)
                if text is None:
                    logger.info(
                        "report repo=%s org_id=%s schedule=%s status=skipped-empty",
                        repo, org_id, schedule_name,
                    )
                    skipped_empty += 1
                    continue

                if plan.telegram_channel is None:
                    logger.info(
                        "report repo=%s org_id=%s schedule=%s status=skipped-no-channel",
                        repo, org_id, schedule_name,
                    )
                    skipped_no_channel += 1
                    continue

                await delivery.deliver(plan, text)
                logger.info(
                    "report repo=%s org_id=%s schedule=%s status=delivered",
                    repo, org_id, schedule_name,
                )
                delivered += 1
            except Exception:
                # A single repo's failure (mirror.ensure network/auth error,
                # a missing GITHUB_ORG_LOGINS entry, an LLM timeout inside
                # build) must not starve the other served repos of their
                # report this cadence — log and move on; a transient
                # failure recovers on the next scheduled run.
                logger.exception(
                    "report repo=%s org_id=%s schedule=%s status=failed",
                    repo, org_id, schedule_name,
                )
                failed += 1

        logger.info(
            "report run complete: schedule=%s delivered=%d skipped_empty=%d "
            "skipped_no_channel=%d failed=%d",
            schedule_name, delivered, skipped_empty, skipped_no_channel, failed,
        )
    finally:
        await pool.close()


def main() -> None:
    args = parse_args()
    asyncio.run(_run(args.schedule))


if __name__ == "__main__":
    main()
