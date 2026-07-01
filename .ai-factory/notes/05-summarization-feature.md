# summarization/ Feature — PromptBuilder + Summarizer

**Date:** 2026-07-01
**Source:** conversation context

## Key Findings

- Nothing turns a `CommitContext` into human-readable release notes. This is the actual value of the whole project — the piece the user cares about ("decent notes, not garbage").
- This task adds the `summarization/` feature: a `PromptBuilder` that renders a `CommitContext` into a prompt, and a `Summarizer` that takes an injected `LLMClient` + `PromptBuilder` and returns the summary text.

## Details

### Current state
Task 03 produces `CommitContext`; task 04 provides `LLMClient`. Nothing connects them.

### Target
- `src/summarization/__init__.py`
- `src/summarization/prompt.py`:
  ```python
  class PromptBuilder:
      def build(self, context: CommitContext, lang: str = "ru") -> str: ...
  ```
  First prompt version renders, per commit: subject + body, changed file paths (the projection of project structure), and the diffstat; then instructs the model to produce concise release notes in `lang`. Prompt text lives here as a template, never inline in the service.
- `src/summarization/service.py`:
  ```python
  class Summarizer:
      def __init__(self, llm: LLMClient, prompt: PromptBuilder) -> None:
          self._llm = llm
          self._prompt = prompt
      async def summarize(self, context: CommitContext, lang: str = "ru") -> str:
          return await self._llm.generate(self._prompt.build(context, lang))
  ```

### Architecture notes
Strict constructor DI: `Summarizer` never constructs an `OllamaClient` — it receives an `LLMClient`. Prompt construction (a distinct responsibility, likely to churn heavily during quality iteration) is isolated in `PromptBuilder` so the service orchestration stays stable while prompts evolve. This SRP split is what makes the eval loop (task 07) able to swap prompts without touching the service.

### Guards
- No LLM instantiation inside the feature — wiring happens only at the composition root (task 06).
- No prompt strings inline in `service.py`.
- `lang` defaults to `ru` (dev branch is always RU per project rules).

### Verify
- Given a real `CommitContext` (from task 03) and an injected `OllamaClient`, `await Summarizer(...).summarize(ctx)` returns a coherent Russian summary that references the actual changes.

## Open Questions

- Prompt quality is the open research problem — this task lands a first working prompt; the eval harness (task 07) and the "Quality feedback loop" phase iterate it. Two-stage summarization (per-commit → digest) is a later phase, not this task.
