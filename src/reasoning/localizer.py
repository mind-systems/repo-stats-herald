import typing
from abc import ABC, abstractmethod

from src.episodic.linked_change import LinkedChange
from src.reasoning.reasoner import Reasoner
from src.reasoning.translator import Translator


class ReportProtocol(typing.Protocol):
    """Structural shape a `Localizer` needs from `changelog.Report` —
    declared here (not imported) so `reasoning` never depends on
    `changelog`, keeping the `changelog → reasoning` dependency one-way."""

    async def build(self, repo: str, org_id: int, lang: str = "ru") -> str | None: ...


class Localizer(ABC):
    """The swap seam for producing one narration note per requested
    language for a single `LinkedChange` — callers depend on this single
    `notes` surface and never know whether a strategy reasons natively in
    every language or reasons once and translates the rest."""

    @abstractmethod
    async def notes(self, change: LinkedChange, langs: set[str]) -> dict[str, str]: ...

    @abstractmethod
    async def report_notes(
        self, report: ReportProtocol, repo: str, org_id: int, langs: set[str]
    ) -> dict[str, str | None]: ...


class PivotLocalizer(Localizer):
    """Reasons once, in a single pivot language, then translates that one
    narration out to every other requested language.

    `notes` calls `Reasoner.narrate` exactly once, for `pivot`, regardless of
    how many languages are requested — every other requested language is
    produced by calling `Translator.translate` on that single narration with
    `source_lang=` the configured `pivot`. When `pivot` itself is among the
    requested `langs`, its entry in the result is the raw `narrate` output,
    never routed through `translate`. When `pivot` is not requested, it is
    still generated once as the intermediate but does not appear in the
    result. An empty `langs` yields an empty dict without narrating or
    translating anything — the pivot is never generated speculatively.
    """

    def __init__(self, reasoner: Reasoner, translator: Translator, pivot: str = "en") -> None:
        self._reasoner = reasoner
        self._translator = translator
        self._pivot = pivot

    async def notes(self, change: LinkedChange, langs: set[str]) -> dict[str, str]:
        if not langs:
            return {}

        narration = await self._reasoner.narrate(change, self._pivot)

        result: dict[str, str] = {}
        for lang in langs:
            if lang == self._pivot:
                result[lang] = narration
            else:
                result[lang] = await self._translator.translate(
                    narration, target_lang=lang, source_lang=self._pivot
                )
        return result

    async def report_notes(
        self, report: ReportProtocol, repo: str, org_id: int, langs: set[str]
    ) -> dict[str, str | None]:
        """Mirrors `notes` exactly, substituting `report.build(repo, org_id,
        lang)` for `reasoner.narrate(change, lang)`: `report.build` is called
        **once**, for `pivot`, regardless of how many languages are
        requested. When that pivot build returns `None` (every section in
        the report was empty), every requested language maps to `None` and
        `translate` is never called — there is no text to translate. An
        empty `langs` yields an empty dict without building or translating
        anything."""
        if not langs:
            return {}

        pivot_text = await report.build(repo, org_id, self._pivot)

        if pivot_text is None:
            return {lang: None for lang in langs}

        result: dict[str, str | None] = {}
        for lang in langs:
            if lang == self._pivot:
                result[lang] = pivot_text
            else:
                result[lang] = await self._translator.translate(
                    pivot_text, target_lang=lang, source_lang=self._pivot
                )
        return result


class NativeLocalizer(Localizer):
    """Reasons independently in every requested language — no pivot, no
    translation step.

    `notes` calls `Reasoner.narrate` once per language in `langs`, each with
    that language passed as `lang`, and returns each result under its own
    language key. An empty `langs` yields an empty dict without narrating
    anything.
    """

    def __init__(self, reasoner: Reasoner) -> None:
        self._reasoner = reasoner

    async def notes(self, change: LinkedChange, langs: set[str]) -> dict[str, str]:
        return {lang: await self._reasoner.narrate(change, lang) for lang in langs}

    async def report_notes(
        self, report: ReportProtocol, repo: str, org_id: int, langs: set[str]
    ) -> dict[str, str | None]:
        """One `report.build` call per requested language, each
        independently possibly `None` — no translation. An empty `langs`
        yields an empty dict without building anything."""
        return {lang: await report.build(repo, org_id, lang) for lang in langs}
