"""Composition root: distill a code-only repo's current HEAD into a
human-reviewable semantic-bootstrap draft.

Run as a module from the project root:

    uv run python -m scripts.bootstrap --repo <name> --org-id <id>
"""

import argparse
import asyncio
from pathlib import Path

from src.core.config import get_settings
from src.github.app_auth import GitHubAppAuth
from src.github.mirror import RepoMirror
from src.knowledge.bootstrap import CodeBootstrap
from src.knowledge.code_distiller import CodeDistiller
from src.knowledge.code_source_strategy import CodeSourceStrategy
from src.llm.client import OllamaClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Distill a code-only repo's current HEAD into a semantic-bootstrap draft.",
    )
    parser.add_argument("--repo", required=True, help="Repo name")
    parser.add_argument("--org-id", dest="org_id", required=True, type=int, help="GitHub org id")
    return parser.parse_args()


async def _run(repo: str, org_id: int) -> None:
    settings = get_settings()

    pem = Path(settings.github_app_private_key_path).read_text()
    auth = GitHubAppAuth(settings.github_app_id, pem)

    def clone_source(repo: str, org_id: int) -> str:
        login = settings.github_org_logins.get(org_id)
        if login is None:
            raise LookupError(f"no GITHUB_ORG_LOGINS entry for org_id={org_id}")
        return f"https://github.com/{login}/{repo}.git"

    mirror = RepoMirror(Path(settings.mirror_root), auth, clone_source)
    await mirror.sweep_worktrees()

    distiller = CodeDistiller(OllamaClient(settings.ollama_url, settings.ollama_model, settings.ollama_api_key))
    strategy = CodeSourceStrategy()

    bootstrap = CodeBootstrap(mirror, distiller, strategy, Path(settings.bootstrap_draft_root))
    await bootstrap.run(repo, org_id)


def main() -> None:
    args = parse_args()
    asyncio.run(_run(args.repo, args.org_id))


if __name__ == "__main__":
    main()
