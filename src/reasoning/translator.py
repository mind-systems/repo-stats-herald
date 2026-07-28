from abc import ABC, abstractmethod

from src.llm.client import LLMClient

_TRANSLATE_TEMPLATE = (
    "Translate the following text from {source_lang} into {target_lang}.\n\n"
    "Preserve identifiers and proper nouns untranslated — feature names, "
    "repository names, and code symbols must read the same in the "
    "translation as in the source text.\n\n"
    "Return only the translated text, with no preamble or commentary.\n\n"
    "Text:\n{text}"
)


class Translator(ABC):
    """The swap seam for turning text authored in one language into another —
    the same abstraction discipline as `LLMClient`: callers reason and narrate
    in a single pivot language, then hand the result here to reach every other
    requested language, without this seam naming which backend does the work.
    """

    @abstractmethod
    async def translate(self, text: str, target_lang: str, source_lang: str = "en") -> str: ...


class LLMTranslator(Translator):
    """`Translator` backed by an injected `LLMClient` — the same
    model-agnostic seam `Summarizer`/`Reasoner` depend on; this class never
    constructs a concrete backend itself."""

    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    async def translate(self, text: str, target_lang: str, source_lang: str = "en") -> str:
        prompt = self._build_prompt(text, target_lang, source_lang)
        return await self._llm.generate(prompt)

    def _build_prompt(self, text: str, target_lang: str, source_lang: str) -> str:
        return _TRANSLATE_TEMPLATE.format(text=text, target_lang=target_lang, source_lang=source_lang)
