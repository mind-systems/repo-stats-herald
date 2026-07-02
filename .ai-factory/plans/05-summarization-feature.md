# Plan: summarization/ feature

## Context
Adds the `summarization/` feature that turns a `CommitContext` into human-readable release notes — the core value of the project. A `PromptBuilder` renders the context into an LLM prompt, and a `Summarizer` (injected `LLMClient` + `PromptBuilder`) returns the summary text.

## Settings
- Testing: no
- Logging: minimal
- Docs: no

## Codebase Notes
- `src/commits/models.py` defines `CommitContext(repo, branch, commits: tuple[Commit, ...])` and `Commit(sha, author, message, changed_files: tuple[str, ...], diffstat)`. `message` already combines subject + body (subject, then blank line, then body), so the prompt uses `commit.message` directly rather than separate subject/body fields.
- `src/llm/client.py` defines `LLMClient` (ABC) with `async def generate(self, prompt: str) -> str` and its `OllamaClient` implementation. `Summarizer` must depend only on the abstract `LLMClient`.
- Feature-modular layout (per ARCHITECTURE.md): one package under `src/`, owning its own files. No env reads, no concrete client construction inside the feature — wiring happens at the composition root (task 06).

## Tasks

### Phase 1: Feature package

- [x] **Task 1: Create summarization package init**
  Files: `src/summarization/__init__.py`
  Add an empty package marker (mirrors `src/commits/__init__.py` and `src/llm/__init__.py`), so `src.summarization` is importable.

- [x] **Task 2: Implement PromptBuilder**
  Files: `src/summarization/prompt.py`
  Add `class PromptBuilder` with `def build(self, context: CommitContext, lang: str = "ru") -> str`. Import `CommitContext` from `src.commits.models`. Render, per commit, the commit message (`commit.message`), the changed file paths (`commit.changed_files`), and the diffstat (`commit.diffstat`); include repo/branch header from `context.repo` / `context.branch`. Append an instruction directing the model to produce concise release notes written in `lang`. Keep all prompt text as module-level template constants / f-strings inside this file — never inline in the service. Do not call any LLM here; `build` returns a plain string. Follow existing style (type hints, no external deps).

- [x] **Task 3: Implement Summarizer service** (depends on Task 2)
  Files: `src/summarization/service.py`
  Add `class Summarizer` with `def __init__(self, llm: LLMClient, prompt: PromptBuilder) -> None` storing both as private attributes, and `async def summarize(self, context: CommitContext, lang: str = "ru") -> str` that returns `await self._llm.generate(self._prompt.build(context, lang))`. Import `LLMClient` from `src.llm.client`, `PromptBuilder` from `src.summarization.prompt`, `CommitContext` from `src.commits.models`. Strict constructor DI — never instantiate `OllamaClient` or any concrete client here; no prompt strings inline (all prompt text stays in `PromptBuilder`). `lang` defaults to `"ru"`.
