# Code Review: 05 — summarization/ feature

## Scope
Reviewed the staged changes for the `summarization/` feature:
- `src/summarization/__init__.py` (empty package marker)
- `src/summarization/prompt.py` (`PromptBuilder`)
- `src/summarization/service.py` (`Summarizer`)

Read against `src/commits/models.py`, `src/llm/client.py`, and `ARCHITECTURE.md`.

## Correctness

- **Imports resolve.** `Commit`/`CommitContext` exist in `src.commits.models`; `LLMClient` in `src.llm.client`; `PromptBuilder` in `src.summarization.prompt`. All import paths are valid.
- **`Summarizer.summarize` awaits `generate`.** `LLMClient.generate` is `async`; the service correctly `await`s it and the coroutine chain is sound.
- **`str.format` is safe here — no format-injection.** `_COMMIT_TEMPLATE.format(...)`, `_HEADER_TEMPLATE.format(...)`, and `_INSTRUCTION_TEMPLATE.format(...)` are applied to the fixed template literals only; the substituted values (commit `message`, `changed_files`, `diffstat`, `repo`, `branch`, `lang`) are inserted, not re-parsed. A commit message containing literal `{...}` cannot break `format` or inject placeholders.
- **Empty-commit-tuple degrades gracefully.** When `context.commits == ()`, `"\n".join(...)` yields `""` and `build` returns a well-formed prompt (header + instruction) rather than crashing — satisfies the empty-range guard.
- **Types line up.** `changed_files` is `tuple[str, ...]`; `", ".join(...)` with the `"none"` fallback is correct. `diffstat` is a `str` and interpolates directly (an empty diffstat leaves a cosmetically trailing space — not a defect).

## Architecture / guards
- `Summarizer` depends only on the abstract `LLMClient`; no `OllamaClient` or any concrete client is constructed inside the feature. ✅
- All prompt text lives in module-level templates in `prompt.py`; none inline in `service.py`. ✅
- No env reads / `Settings` access inside the feature; wiring is left to the composition root. ✅
- `lang` defaults to `"ru"` in both `build` and `summarize`. ✅

## Runtime concerns
No missing migrations (pure in-process logic, no DB), no type mismatches, no race conditions, no blocking calls in the async path.

## Findings
None. The implementation matches the plan and the spec, and I found no correctness, security, or runtime defects.

REVIEW_PASS
