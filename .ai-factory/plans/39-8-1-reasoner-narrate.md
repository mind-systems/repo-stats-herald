# Plan: 8.1 — Reasoner narrate

## Context
Add `Reasoner.narrate(change, lang)` — the broadcast projection of the reasoner: it reuses the existing `_gather_context` retrieval+neighbor helper (7.1/7.2) and a new narration prompt to turn a resolved `LinkedChange` into feature-level prose, so narration never re-implements retrieval, neighbor discovery, or a second `LLMClient` call. Also register a `narrate` eval-harness handler so the note is verified against a reference like every other prose producer.

## Settings
- Testing: minimal (only the silent-failure surfaces the spec's guards call out: query construction from both sources, and the commits-only floor — mockable, no real LLM)
- Logging: minimal
- Docs: no

## Tasks

### Phase 1: Narration prompt

- [x] **Task 1: Add the narration prompt builder**
  Files: `src/reasoning/narration_prompt.py`
  Add a `NarrationPromptBuilder` class that owns all narration prompt text (mirroring how `ReasoningPromptBuilder` in `src/reasoning/prompt.py` and `PromptBuilder` in `src/summarization/prompt.py` encapsulate their own prompt strings — never inline in the reasoner).
  - `build(self, change: LinkedChange, chunks: list[Chunk], entries: list[EpisodicEntry], neighbor_chunks: list[Chunk], lang: str = "ru") -> str`.
  - Frame this as **narration, not Q&A** (distinct from `ReasoningPromptBuilder`, which asks a question): completed tasks lead as intent+outcome, the commit messages in `change.commits` are supporting detail, and cross-project neighbors are framed as what the change **"unblocks"** — only where `neighbor_chunks` is non-empty (otherwise the note stays single-project).
  - Instruction must demand **prose at the feature level, never bullets or a raw diff**, generated **in `lang`** (reuse the `in {lang}` pattern from `PromptBuilder._INSTRUCTION_TEMPLATE`).
  - **Fallback:** where `change.completed_tasks` is empty, the prompt anchors on a commit-level digest instead of leading with tasks (same discipline the superseded narrator had) — a coherent digest, never a fabricated feature.
  - Render commits from `change.commits.commits` (each `Commit.message`, `src/commits/models.py`); render chunks/entries/neighbors following the section shapes already established in `ReasoningPromptBuilder._render_chunk` / `_render_entry` / `_render_neighbor_chunks` so the two builders stay consistent.
  - Import `LinkedChange` from `src/episodic/linked_change.py`, `Chunk` from `src/knowledge/store.py` (only `Chunk` — the builder renders chunks but references no store, matching `ReasoningPromptBuilder`'s import), `EpisodicEntry` from `src/episodic/models.py`.

### Phase 2: Reasoner.narrate

- [x] **Task 2: Add `narrate` to the reasoner** (depends on Task 1)
  Files: `src/reasoning/reasoner.py`
  - Inject the builder: add an optional `narration_prompt: NarrationPromptBuilder | None = None` constructor parameter alongside the existing `prompt`, defaulting to `NarrationPromptBuilder()` when `None` (same pattern as the current `prompt` default). Store as `self._narration_prompt`. Do **not** change the existing `prompt` parameter or `answer`.
  - Add `async def narrate(self, change: LinkedChange, lang: str = "ru") -> str`:
    1. Build the retrieval query from **both** `change.completed_tasks` (a `tuple[str, ...]` of done-marker ids) **and** the commit messages in `change.commits` (`CommitContext`; each `Commit.message`) — join both into one query string via a small private helper (e.g. `_narration_query(change)`). Neither source is dropped when the other is empty; when `completed_tasks` is empty the commit messages still drive retrieval, and vice versa.
    2. Call the **shared** `await self._gather_context(query, change.repo)` — the same helper `answer` uses (7.1 retrieval + 7.2 neighbor folding), scoped to the bare `change.repo` key (`linked_change.py:21`), reusing the injected `Settings.reasoner_k`. Do **not** add any second retrieval or neighbor mechanism, and do **not** call `answer` (it returns finished Q&A prose, not context).
    3. Build the prompt via `self._narration_prompt.build(change, gathered.chunks, gathered.entries, gathered.neighbor_chunks, lang)`.
    4. `return await self._llm.generate(prompt)`.
  - **Commits-are-the-floor:** because `change.commits` always populates the query and the prompt, `narrate` never returns empty. `_gather_context` already isolates per-store and per-neighbor failures (degrading to a surviving store / empty context, never raising), so the degradation ladder — full context → surviving store's context → commits-only digest — holds without extra handling here. Do not add try/except around `_gather_context`; its internal isolation is the mechanism.
  - Import `LinkedChange` and `NarrationPromptBuilder`.

### Phase 3: Eval handler

- [x] **Task 3: Register the `narrate` eval case-type handler** (depends on Task 2)
  Files: `scripts/eval.py`
  - Add a `NarrateCaseHandler(CaseHandler)` next to `ReasonerCaseHandler`. Constructor takes a `LinkedChangeResolver` and a `Reasoner`. In `run(inputs)`: split `inputs["range"]` into `before`/`after` with `rsplit("..", 1)` and assert exactly two parts (matching how `resolver.resolve` reconstructs `f"{before}..{after}"`; a two-dot range like `"HEAD~3..HEAD"` splits cleanly, and the guard surfaces a malformed range instead of silently mis-splitting), call `resolver.resolve(inputs["repo"], before, after)` to build the `LinkedChange`, then `return await self._reasoner.narrate(change, inputs.get("lang", "ru"))`. This makes the harness case a real registered producer, not a manual check.
  - Wire at the composition root in `_run()`: the `narrate` case type needs the DB pool exactly like `reasoner`, so widen the pool-gating condition to also fire when any case has `type == "narrate"`, and build the `Reasoner` once (reuse it for both `reasoner` and `narrate` handlers rather than constructing twice).
  - Construct the resolver: `LinkedChangeResolver(GitCommitCollector(), AiFactorySourceStrategy())` — the ai-factory strategy supplies `roadmap_paths()` (the resolver reads the roadmap to derive `completed_tasks`); `CodeSourceStrategy` returns `()` and would starve task derivation, so use `AiFactorySourceStrategy` here. Register `handlers["narrate"] = NarrateCaseHandler(resolver, reasoner)`.
  - Add imports: `LinkedChangeResolver` from `src/episodic/linked_change.py`, `AiFactorySourceStrategy` from `src/knowledge/source_strategy.py` (`GitCommitCollector` is already imported).

### Phase 4: Guard tests

- [x] **Task 4: Unit tests for query construction and the commits floor** (depends on Task 2)
  Files: `tests/reasoning/test_narrate.py`
  Reuse the existing fakes/fixtures in `tests/reasoning/conftest.py` (`reasoner`, `fake_embedder`, `fake_knowledge`, `fake_episodic`, `fake_llm`, `make_chunk`). Build small `LinkedChange`/`CommitContext`/`Commit` values inline. Assert only the silent-failure surfaces the spec pins:
  - A change with completed tasks → the constructed retrieval query (assert on `fake_embedder.calls[0]`) includes the task text.
  - A commits-only change (empty `completed_tasks`) → the query still includes the commit messages — retrieval is not starved by an empty task list.
  - A mocked store-retrieval failure (`fake_knowledge.error` / `fake_episodic.error` set) → `narrate` still returns non-empty text (the commits-only floor holds), never raises.
  - No neighbors surfaced → single-project note: `gathered.neighbor_chunks` is empty, so no per-neighbor knowledge fetch fires and the prompt carries no "unblocks" section. (Do **not** assert on total `fake_knowledge.calls` count: `_gather_context` always issues the repo-scoped query **and** the org-wide discovery query `query(embedding, k, repo=None)` for any non-None `repo`, and `change.repo` is always a bare non-None `str` — so two knowledge calls fire even with zero neighbors. Only the per-neighbor fetch is conditional.)
  Do not assert exact prompt wording or `k`'s value — leave prose quality to the eval harness, matching the discipline in `test_reasoner_contract.py`.
