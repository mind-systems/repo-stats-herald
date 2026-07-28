from abc import ABC, abstractmethod


class Translator(ABC):
    """The swap seam for turning text authored in one language into another —
    the same abstraction discipline as `LLMClient`: callers reason and narrate
    in a single pivot language, then hand the result here to reach every other
    requested language, without this seam naming which backend does the work.
    """

    @abstractmethod
    async def translate(self, text: str, target_lang: str, source_lang: str = "en") -> str: ...


class StubTranslator(Translator):
    """Placeholder `Translator` — raises until the real implementation lands."""

    async def translate(self, text: str, target_lang: str, source_lang: str = "en") -> str:
        raise NotImplementedError
