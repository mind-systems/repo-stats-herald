# Plan: 7.1.2 — Reasoner core (impl)

## Context
Turn 7.1.1's red retrieval-invariant tests green by implementing `Reasoner.answer`'s real reasoning path — embed once, query both memories through a reusable `_gather_context` helper, build a grounded reasoning prompt, and call `LLMClient.generate` — then wire the reasoner at the eval composition root and verify prose quality against a user-authored reference.

## Settings
- Testing: no
- Logging: minimal
- Docs: no

## Key facts established from the code (ground truth)

- `src/reasoning/reasoner.py` already has the constructor DI shape `Reasoner(llm, embedder, knowledge, episodic)` and the `answer(query, repo=None)` signature; `answer` is a stub that raises `NotImplementedError`.
- The 7.1.1 fixture `tests/reasoning/conftest.py::reasoner` constructs `Reasoner(llm=…, embedder=…, knowledge=…, episodic=…)` with **exactly those four keyword args**. Any new constructor parameter (`reasoner_k`, prompt builder) **must have a default**, or the fixture — and every 7.1.1 test — breaks at construction.
- No 7.1.1 test asserts on `k`'s value, exact prompt text, or combined-context format (per the suite's own docstring), so those stay design choices here.
- Collaborator signatures are fixed: `Embedder.embed(texts) -> list[list[float]]`; `KnowledgeStore.query(embedding, k, repo=None) -> list[Chunk]`; `EpisodicStore.query(embedding, k, repo=None, since=None, until=None) -> list[EpisodicEntry]`; `LLMClient.generate(prompt) -> str`. `Chunk` carries `content/repo/path/chunk_index`; `EpisodicEntry` carries `content/repo/changed_at/completed_tasks/commit_shas`.
- No composition root constructs a `Reasoner` yet. `scripts/eval.py` is the offline composition root (currently sync `main()`), and its own docstring says later prose producers each ship a `CaseHandler` registered in `main()`. `scripts/backfill_episodic.py` shows the async pool-wiring pattern (`create_pool(settings.postgres_dsn)` from `src/core/db.py`, `try/finally: await pool.close()`).
- The summarization feature encapsulates prompt text in a dedicated `PromptBuilder` (`src/summarization/prompt.py`) injected into `Summarizer` — the convention this plan mirrors for the reasoner.

## Design decisions (resolving spec ↔ code tension)

- **`reasoner_k` is a constructor parameter with default `8`**, read from `Settings.reasoner_k` and injected at the composition root — never read from env inside the reasoner. The default keeps the 7.1.1 fixture (four args) green while the eval/composition root injects `settings.reasoner_k`. The same `k` value feeds **both** store queries.
- **Prompt text lives in a dedicated `ReasoningPromptBuilder`** (new `src/reasoning/prompt.py`), matching the mandated "prompt strings live in PromptBuilder" convention and the `Summarizer`/`PromptBuilder` shape. It is an **optional** constructor arg on `Reasoner` defaulting to a fresh `ReasoningPromptBuilder()` — keeping the 7.1.1 fixture green while staying injectable at the root.
- **`ReasoningPromptBuilder.build` takes the domain value objects directly** — `build(query: str, chunks: list[Chunk], entries: list[EpisodicEntry]) -> str`, importing `Chunk` from `src/knowledge/store.py` and `EpisodicEntry` from `src/episodic/models.py`. This mirrors `PromptBuilder.build(CommitContext)` (a value object owned by *another* module) and **avoids an import cycle**: `GatheredContext` is defined in and owned by `reasoner.py`, which already imports `prompt.py`; if `prompt.py` took `GatheredContext` it would import back from `reasoner.py` and fail at module load. `answer` unpacks its `GatheredContext` into the value-object call. `GatheredContext` therefore stays internal to `reasoner.py` (used only as `answer`'s return-shape from `_gather_context`) and is never imported by `prompt.py`.
- **Honest no-memory path = Resolution B (marked prompt).** `answer` always calls `generate`, but when both memories are empty the prompt carries an explicit no-memory framing distinct from a grounded prompt. This satisfies both the "distinguishable path" test and `test_both_stores_failing_falls_back_to_no_memory_path` (both-empty and both-raise produce the *same* no-memory prompt → identical `generate` call), and lets the LLM phrase the honest "no memory for this project" answer.
- **Per-store failure isolation lives in `_gather_context`.** Each store query is wrapped independently; a raised exception is treated as "empty results from that store" (logged at minimal level), never re-raised. Embedding happens once before both queries and is not part of the store-degradation guard (spec scopes degradation to the two stores).

## Tasks

### Phase 1: Config

- [x] **Task 1: Add `Settings.reasoner_k` and document it**
  Files: `src/core/config.py`, `.env.example`
  Add `reasoner_k: int = 8` to `Settings` (place it near the other retrieval/LLM fields). Add a `REASONER_K=8` line to `.env.example` with a one-line comment: the retrieval size used for **both** the knowledge and episodic store queries in the reasoner. No validator needed (plain int, pydantic-settings coerces from env).

### Phase 2: Reasoner implementation

- [x] **Task 2: Add the reasoning prompt builder** (depends on Task 1)
  Files: `src/reasoning/prompt.py` (new)
  Create `ReasoningPromptBuilder` mirroring `src/summarization/prompt.py` (module-level template constants + a `build(...)` method; owns all prompt strings). **Signature: `build(query: str, chunks: list[Chunk], entries: list[EpisodicEntry]) -> str`**, importing `Chunk` from `src/knowledge/store.py` and `EpisodicEntry` from `src/episodic/models.py` — value objects owned by *other* feature modules, exactly as `PromptBuilder.build` takes `CommitContext`. **Do not** take `GatheredContext` (owned by `reasoner.py`) as the argument — that forms a `reasoner → prompt → reasoner` import cycle. It renders a reasoning prompt from: the user `query`, the retrieved semantic chunks (what the project *is* now — render each chunk's `content`, optionally its `repo`/`path` for grounding), and the retrieved episodic entries (how it *changed* — render each entry's `content` alongside its `changed_at`, so the LLM can reason over timing without any explicit `since`/`until` window). Instruct feature-level, grounded prose that answers the question only from the supplied memory. When **both** lists are empty, `build` emits an explicit no-memory framing ("no standing memory for this project — say so honestly, do not fabricate") — materially different text from any grounded prompt, so the two are distinguishable. (Handle the empty-both branch inside `build` on the same value-object signature, e.g. an internal `if not chunks and not entries` branch.)

- [x] **Task 3: Implement `_gather_context` and `answer`** (depends on Task 2)
  Files: `src/reasoning/reasoner.py`
  - Extend `__init__` to accept `reasoner_k: int = 8` and an optional `prompt: ReasoningPromptBuilder | None = None` (default to a fresh `ReasoningPromptBuilder()`); store both. **Keep the existing four collaborator params and their keyword-usable names unchanged** so the 7.1.1 fixture still constructs the reasoner.
  - Add a small frozen result type for the gathered memory (e.g. a `GatheredContext` dataclass holding `chunks: list[Chunk]` and `entries: list[EpisodicEntry]`) so 7.2 (neighbor folding) and 8.1's `narrate` can extend/reuse one shape.
  - Implement `async def _gather_context(self, query, repo) -> GatheredContext`:
    1. Embed once: `embedding = (await self._embedder.embed([query]))[0]` — reuse this **same object** for both store calls (7.1.1 asserts identity).
    2. Query knowledge: `await self._knowledge.query(embedding, self._k, repo=repo)`, wrapped in try/except → on failure log at minimal level and use `[]`.
    3. Query episodic: `await self._episodic.query(embedding, self._k, repo=repo)` (leave `since`/`until` at their `None` defaults), wrapped the same way → `[]` on failure.
    4. Return `GatheredContext(chunks, entries)`.
    Pass `repo` through unchanged to both queries — the bare `push.repo` key or `None`, never defaulted.
  - Implement `async def answer(self, query, repo=None) -> str`: call `_gather_context`, unpack the `GatheredContext` into the value-object prompt call `self._prompt.build(query, gathered.chunks, gathered.entries)` (the builder itself picks grounded vs no-memory framing from whether the lists are empty), then `return await self._llm.generate(prompt)`. Always reach `generate` (Resolution B).
  - Remove the `NotImplementedError`; update the class/method docstring to describe the implemented behavior in present tense (no plan/phase references in comments).

- [x] **Task 4: Confirm the 7.1.1 suite is green** (depends on Task 3)
  Files: (verification only — `tests/reasoning/test_reasoner_contract.py`, unchanged)
  Run `uv run pytest tests/reasoning/` and confirm all 7.1.1 tests pass without editing them. This is the retrieval-invariant gate; do not add or modify tests. If any test fails, the failure points at a deviation from the pinned invariants (embedding identity, bare-`repo` passthrough, no-memory distinguishability, per-store failure isolation) — fix the implementation, not the test.

### Phase 3: Composition-root wiring & eval

- [x] **Task 5: Wire the reasoner into the eval composition root** (depends on Task 3)
  Files: `scripts/eval.py`
  Add a `ReasonerCaseHandler(CaseHandler)` whose `run(inputs)` calls `await self._reasoner.answer(inputs["query"], inputs.get("repo"))` and returns the text (owns no filename logic, per the existing handler contract). Restructure `main()` into an async `_run()`, loading cases first. **Scope the Postgres pool to reasoner cases so the existing `summary`/`distill` cases keep running without a database** — today `make eval` needs only the Ollama tunnel, and Task 5 must not newly couple those cases to Postgres. Only when a `type: reasoner` case is present in the loaded cases: `pool = await create_pool(settings.postgres_dsn)` under a `try/finally: await pool.close()` (mirroring `scripts/backfill_episodic.py`), build the concretes — `OllamaClient`, `OllamaEmbedder(settings.ollama_url, settings.embed_model, settings.ollama_api_key)`, `PgVectorStore(pool)`, `PgEpisodicStore(pool)` — construct the `Reasoner` injecting `reasoner_k=settings.reasoner_k` and the prompt builder, and register `"reasoner"` in the `handlers` dict. The `summary`/`distill` handlers are always registered and never touch the pool; when no reasoner case is loaded, no pool is opened at all. `main()` becomes `asyncio.run(_run())`.

- [x] **Task 6: Add the reasoner eval case (no fabricated reference)** (depends on Task 5)
  Files: `evals/cases.yaml`
  Add one `type: reasoner` case with `name`, `repo` (a bare `push.repo` key whose memory is populated in the local Postgres stores — e.g. a repo that has been run through `backfill_episodic`/knowledge backfill), and `query`. Add a comment, mirroring the `tradeoxy-features` case, stating that (a) the comparison reference `evals/reference/<name>.md` is **user-authored — never fabricated by the implementer**, same discipline as the summarization/distillation evals, and (b) the case requires that repo's knowledge + episodic stores to be populated (backfill run) before `make eval` yields a grounded answer. **Do not create or write `evals/reference/<name>.md`** — leave the reference for the user to author.
