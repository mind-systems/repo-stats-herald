"""Composition root: replay a served repo's full history into its episodic
log.

Run as a module from the project root:

    uv run python -m scripts.backfill_episodic --repo <name> --org-id <id>
"""

import argparse
import asyncio
from pathlib import Path

from src.commits.collector import GitCommitCollector
from src.core.config import get_settings
from src.core.db import create_pool
from src.episodic.backfill import EpisodicBackfill
from src.episodic.linked_change import LinkedChangeResolver
from src.episodic.store import PgEpisodicStore
from src.github.app_auth import GitHubAppAuth
from src.github.mirror import RepoMirror
from src.knowledge.source_strategy import AiFactorySourceStrategy
from src.llm.embedder import OllamaEmbedder

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "src" / "episodic" / "schema.sql"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill a served repo's episodic log from its full history.",
    )
    parser.add_argument("--repo", required=True, help="Repo name")
    parser.add_argument("--org-id", dest="org_id", required=True, type=int, help="GitHub org id")
    return parser.parse_args()


async def _run(repo: str, org_id: int) -> None:
    settings = get_settings()
    pool = await create_pool(settings.postgres_dsn)
    try:
        async with pool.acquire() as conn:
            await conn.execute(SCHEMA_PATH.read_text())

        embedder = OllamaEmbedder(settings.ollama_url, settings.embed_model, settings.ollama_api_key)
        store = PgEpisodicStore(pool)
        strategy = AiFactorySourceStrategy()
        collector = GitCommitCollector()
        resolver = LinkedChangeResolver(collector, strategy)

        pem = Path(settings.github_app_private_key_path).read_text()
        auth = GitHubAppAuth(settings.github_app_id, pem)

        def clone_source(repo: str, org_id: int) -> str:
            login = settings.github_org_logins.get(org_id)
            if login is None:
                raise LookupError(f"no GITHUB_ORG_LOGINS entry for org_id={org_id}")
            return f"https://github.com/{login}/{repo}.git"

        mirror = RepoMirror(Path(settings.mirror_root), auth, clone_source)

        backfill = EpisodicBackfill(mirror, resolver, embedder, store, collector, settings.canonical_refs)

        await backfill.run(repo, org_id)
    finally:
        await pool.close()


def main() -> None:
    args = parse_args()
    asyncio.run(_run(args.repo, args.org_id))


if __name__ == "__main__":
    main()
