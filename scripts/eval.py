"""Eval harness: run fixed {repo,range,lang} cases through the production
Summarizer/GitCommitCollector and write one stable-named output file per case.

Composition root for offline eval runs — the only place concretes are wired
together, mirroring scripts/summarize_range.py. Run as a module from the
project root:

    uv run python -m scripts.eval
"""

import asyncio
from dataclasses import dataclass
from pathlib import Path

import yaml

from src.commits.collector import GitCommitCollector
from src.core.config import get_settings
from src.llm.client import OllamaClient
from src.summarization.prompt import PromptBuilder
from src.summarization.service import Summarizer

_EVALS_DIR = Path(__file__).resolve().parent.parent / "evals"
_CASES_FILE = _EVALS_DIR / "cases.yaml"
_OUT_DIR = _EVALS_DIR / "out"


@dataclass(frozen=True, slots=True)
class Case:
    name: str
    repo: str
    range: str
    lang: str


class EvalRunner:
    """Runs eval cases through the real collector/summarizer and writes outputs."""

    def __init__(self, summarizer: Summarizer, collector: GitCommitCollector) -> None:
        self._summarizer = summarizer
        self._collector = collector

    async def run(self, cases: list[Case]) -> None:
        _OUT_DIR.mkdir(parents=True, exist_ok=True)
        for case in cases:
            ctx = self._collector.collect(case.repo, case.range)
            summary = await self._summarizer.summarize(ctx, case.lang)
            out_path = _OUT_DIR / f"{case.name}.md"
            out_path.write_text(summary, encoding="utf-8")
            print(f"wrote {out_path}")


def _load_cases() -> list[Case]:
    with _CASES_FILE.open() as f:
        data = yaml.safe_load(f)
    raw_cases = (data or {}).get("cases", []) if isinstance(data, dict) else (data or [])
    return [
        Case(name=c["name"], repo=c["repo"], range=c["range"], lang=c["lang"])
        for c in raw_cases
    ]


def main() -> None:
    settings = get_settings()
    collector = GitCommitCollector()
    summarizer = Summarizer(
        OllamaClient(settings.ollama_url, settings.ollama_model, settings.ollama_api_key),
        PromptBuilder(),
    )
    runner = EvalRunner(summarizer, collector)

    cases = _load_cases()
    asyncio.run(runner.run(cases))


if __name__ == "__main__":
    main()
