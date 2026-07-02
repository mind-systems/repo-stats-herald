from src.commits.models import CommitContext
from src.llm.client import LLMClient
from src.summarization.prompt import PromptBuilder


class Summarizer:
    """Turns a CommitContext into human-readable release notes via an injected LLMClient."""

    def __init__(self, llm: LLMClient, prompt: PromptBuilder) -> None:
        self._llm = llm
        self._prompt = prompt

    async def summarize(self, context: CommitContext, lang: str = "ru") -> str:
        return await self._llm.generate(self._prompt.build(context, lang))
