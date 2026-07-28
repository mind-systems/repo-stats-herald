from abc import ABC, abstractmethod

from src.episodic.linked_change import LinkedChange
from src.reasoning.reasoner import Reasoner
from src.reasoning.translator import Translator


class Localizer(ABC):
    """The swap seam for producing one narration note per requested
    language for a single `LinkedChange` — callers depend on this single
    `notes` surface and never know whether a strategy reasons natively in
    every language or reasons once and translates the rest."""

    @abstractmethod
    async def notes(self, change: LinkedChange, langs: set[str]) -> dict[str, str]: ...


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
        raise NotImplementedError


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
        raise NotImplementedError
