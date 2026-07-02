"""Spike CLI: collect a commit range and print an LLM-generated summary.

Composition root for the hand-runnable slice — the only place concretes are
wired together. Run as a module from the project root:

    uv run python -m scripts.summarize_range --repo . --range HEAD~3..HEAD
"""

import argparse
import asyncio

from src.commits.collector import GitCommitCollector
from src.core.config import get_settings
from src.llm.client import OllamaClient
from src.summarization.prompt import PromptBuilder
from src.summarization.service import Summarizer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize a git commit range using Ollama.",
    )
    parser.add_argument("--repo", required=True, help="Path to the git repository")
    parser.add_argument(
        "--range", dest="range", required=True, help="Rev range, e.g. HEAD~3..HEAD"
    )
    parser.add_argument("--lang", default="ru", help="Summary language (default: ru)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    settings = get_settings()
    collector = GitCommitCollector()
    summarizer = Summarizer(
        OllamaClient(settings.ollama_url, settings.ollama_model, settings.ollama_api_key),
        PromptBuilder(),
    )

    ctx = collector.collect(args.repo, args.range)
    print(asyncio.run(summarizer.summarize(ctx, args.lang)))


if __name__ == "__main__":
    main()
