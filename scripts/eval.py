"""Eval harness: a case-type registry that runs fixed cases through production
composition-root producers and writes one stable-named output file per case.

Each case declares a `type`; the runner dispatches to the `CaseHandler`
registered for that type, which drives the same composition-root producer
used in production and returns the produced text. The `summary` handler
below is today's Summarizer/GitCommitCollector flow; later prose producers
each ship their own `CaseHandler` and register it in `main()` without
editing `EvalRunner`.

Composition root for offline eval runs — the only place concretes are wired
together, mirroring scripts/summarize_range.py. Run as a module from the
project root:

    uv run python -m scripts.eval
"""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

import yaml

from src.commits.collector import GitCommitCollector
from src.core.config import get_settings
from src.core.db import create_pool
from src.episodic.linked_change import LinkedChangeResolver
from src.episodic.store import PgEpisodicStore
from src.graph.store import PgProjectGraph
from src.knowledge.code_distiller import CodeDistiller
from src.knowledge.code_source_strategy import CodeSourceStrategy
from src.knowledge.source_strategy import AiFactorySourceStrategy
from src.knowledge.store import PgVectorStore
from src.llm.client import OllamaClient
from src.llm.embedder import OllamaEmbedder
from src.reasoning.localizer import Localizer, PivotLocalizer
from src.reasoning.prompt import ReasoningPromptBuilder
from src.reasoning.reasoner import Reasoner
from src.reasoning.translator import LLMTranslator
from src.summarization.prompt import PromptBuilder
from src.summarization.service import Summarizer

_EVALS_DIR = Path(__file__).resolve().parent.parent / "evals"
_CASES_FILE = _EVALS_DIR / "cases.yaml"
_OUT_DIR = _EVALS_DIR / "out"


@dataclass(frozen=True, slots=True)
class Case:
    name: str
    type: str
    inputs: dict


class CaseHandler(ABC):
    """Inputs-to-text seam for one case type.

    A handler builds the producer's call from a case's `inputs`, runs the
    already-wired composition-root producer, and returns the produced text.
    It owns no output-file or filename logic — that stays in `EvalRunner`.
    Each producer ships its own `CaseHandler` and registers it at the
    composition root in `main()`; the runner itself is never edited per
    producer.
    """

    @abstractmethod
    async def run(self, inputs: dict) -> str: ...


class SummaryCaseHandler(CaseHandler):
    """Runs the `summary` case type through the production summarizer flow."""

    def __init__(self, summarizer: Summarizer, collector: GitCommitCollector) -> None:
        self._summarizer = summarizer
        self._collector = collector

    async def run(self, inputs: dict) -> str:
        ctx = self._collector.collect(inputs["repo"], inputs["range"])
        return await self._summarizer.summarize(ctx, inputs["lang"])


class DistillCaseHandler(CaseHandler):
    """Runs the `distill` case type through the production code-distiller
    flow, reading a local checkout at `inputs["root"]` in place of a mirror
    tree — the same offline-local-tree substitution `summary` makes for git
    via `repo: "."`."""

    def __init__(self, distiller: CodeDistiller, strategy: CodeSourceStrategy) -> None:
        self._distiller = distiller
        self._strategy = strategy

    async def run(self, inputs: dict) -> str:
        root = Path(inputs["root"])
        selected = []
        for path in root.rglob("*"):
            if not path.is_file() or ".git" in path.parts:
                continue
            rel = path.relative_to(root).as_posix()
            if self._strategy.selects(rel):
                selected.append(rel)

        return await self._distiller.distill(inputs["repo"], selected, root)


class ReasonerCaseHandler(CaseHandler):
    """Runs the `reasoner` case type through the production Reasoner flow."""

    def __init__(self, reasoner: Reasoner) -> None:
        self._reasoner = reasoner

    async def run(self, inputs: dict) -> str:
        return await self._reasoner.answer(inputs["query"], inputs.get("repo"))


class NarrateCaseHandler(CaseHandler):
    """Runs the `narrate` case type through the production
    LinkedChangeResolver + Reasoner.narrate flow."""

    def __init__(self, resolver: LinkedChangeResolver, reasoner: Reasoner) -> None:
        self._resolver = resolver
        self._reasoner = reasoner

    async def run(self, inputs: dict) -> str:
        before, after = self._split_range(inputs["range"])
        change = self._resolver.resolve(inputs["repo"], before, after)
        return await self._reasoner.narrate(change, inputs.get("lang", "ru"))

    def _split_range(self, range_: str) -> tuple[str, str]:
        parts = range_.rsplit("..", 1)
        if len(parts) != 2:
            raise ValueError(f"malformed range (expected 'before..after'): {range_!r}")
        return parts[0], parts[1]


class LocalizeCaseHandler(CaseHandler):
    """Runs the `localize` case type through the production
    LinkedChangeResolver + Localizer flow, rendering one `## <lang>` section
    per requested language."""

    def __init__(self, resolver: LinkedChangeResolver, localizer: Localizer) -> None:
        self._resolver = resolver
        self._localizer = localizer

    async def run(self, inputs: dict) -> str:
        before, after = self._split_range(inputs["range"])
        change = self._resolver.resolve(inputs["repo"], before, after)
        notes = await self._localizer.notes(change, set(inputs["langs"]))
        return "\n\n".join(f"## {lang}\n\n{notes[lang]}" for lang in sorted(notes))

    def _split_range(self, range_: str) -> tuple[str, str]:
        parts = range_.rsplit("..", 1)
        if len(parts) != 2:
            raise ValueError(f"malformed range (expected 'before..after'): {range_!r}")
        return parts[0], parts[1]


class EvalRunner:
    """Dispatches eval cases to their registered handler and writes outputs."""

    def __init__(self, handlers: dict[str, CaseHandler]) -> None:
        self._handlers = handlers

    async def run(self, cases: list[Case]) -> None:
        unregistered = [
            (case.name, case.type) for case in cases if case.type not in self._handlers
        ]
        if unregistered:
            listing = ", ".join(f"{name!r} (type={type_!r})" for name, type_ in unregistered)
            raise ValueError(f"unregistered case type(s): {listing}")

        _OUT_DIR.mkdir(parents=True, exist_ok=True)
        for case in cases:
            text = await self._handlers[case.type].run(case.inputs)
            out_path = _OUT_DIR / f"{case.name}.md"
            out_path.write_text(text, encoding="utf-8")
            print(f"wrote {out_path}")


def _load_cases() -> list[Case]:
    with _CASES_FILE.open() as f:
        data = yaml.safe_load(f)
    raw_cases = (data or {}).get("cases", []) if isinstance(data, dict) else (data or [])
    cases = []
    for c in raw_cases:
        if "name" not in c:
            raise KeyError(f"case missing required 'name' key: {c}")
        if "type" not in c:
            raise KeyError(f"case {c['name']!r} missing required 'type' key")
        inputs = {k: v for k, v in c.items() if k not in ("name", "type")}
        cases.append(Case(name=c["name"], type=c["type"], inputs=inputs))
    return cases


async def _run() -> None:
    cases = _load_cases()
    settings = get_settings()

    collector = GitCommitCollector()
    summarizer = Summarizer(
        OllamaClient(settings.ollama_url, settings.ollama_model, settings.ollama_api_key),
        PromptBuilder(),
    )
    distiller = CodeDistiller(
        OllamaClient(settings.ollama_url, settings.ollama_model, settings.ollama_api_key)
    )
    handlers: dict[str, CaseHandler] = {
        "summary": SummaryCaseHandler(summarizer, collector),
        "distill": DistillCaseHandler(distiller, CodeSourceStrategy()),
    }

    pool = None
    try:
        if any(case.type in ("reasoner", "narrate", "localize") for case in cases):
            pool = await create_pool(settings.postgres_dsn)
            reasoner = Reasoner(
                llm=OllamaClient(settings.ollama_url, settings.ollama_model, settings.ollama_api_key),
                embedder=OllamaEmbedder(settings.ollama_url, settings.embed_model, settings.ollama_api_key),
                knowledge=PgVectorStore(pool),
                episodic=PgEpisodicStore(pool),
                graph=PgProjectGraph(pool),
                reasoner_k=settings.reasoner_k,
                prompt=ReasoningPromptBuilder(),
            )
            handlers["reasoner"] = ReasonerCaseHandler(reasoner)
            handlers["narrate"] = NarrateCaseHandler(
                LinkedChangeResolver(GitCommitCollector(), AiFactorySourceStrategy()), reasoner
            )

            translator = LLMTranslator(
                OllamaClient(settings.ollama_url, settings.ollama_model, settings.ollama_api_key)
            )
            localizer = PivotLocalizer(reasoner, translator, pivot=settings.pivot_lang)
            handlers["localize"] = LocalizeCaseHandler(
                LinkedChangeResolver(GitCommitCollector(), AiFactorySourceStrategy()), localizer
            )

        runner = EvalRunner(handlers)
        await runner.run(cases)
    finally:
        if pool is not None:
            await pool.close()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
