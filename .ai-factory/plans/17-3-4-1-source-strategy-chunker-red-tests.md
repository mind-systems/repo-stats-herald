# Plan: 3.4.1 — Source strategy + chunker (red tests)

## Context
Define the `SourceStrategy` seam (`selects(path) -> bool`, default ai-factory profile) and `chunk_markdown` (whole sections by heading) as pure, I/O-free code with raising stubs, and pin their behavior with red unit tests — ahead of the 3.4.2 indexer implementation. This is a tests-first task: bodies stay unimplemented so the added suite is red; 3.4.2 greens it without re-deciding selection/chunking logic.

## Settings
- Testing: yes (red tests are the deliverable)
- Logging: none
- Docs: no

## Tasks

### Phase 1: Seam & stub definitions

- [x] **Task 1: `SourceStrategy` seam + default ai-factory profile stub**
  Files: `src/knowledge/source_strategy.py`
  Add a `SourceStrategy` ABC (mirror the ABC style of `KnowledgeStore` / `LLMClient` / `Embedder` — plain class name, no `I` prefix, `abc.ABC` + `@abstractmethod`) exposing a single abstract method `selects(self, path: str) -> bool` with a docstring stating it decides which repo-relative paths define the project. Add the concrete default profile as a subclass — name it `AiFactorySourceStrategy(SourceStrategy)` — whose `selects` body is a raising stub (`raise NotImplementedError`), so tests instantiating it and calling `selects` go red. Document in the class docstring the intended selection contract so 3.4.2 implements against it, without implementing it here:
  - **Selected:** `CLAUDE.md` and `AGENTS.md` at the repo root; `ARCHITECTURE.md` and `ROADMAP.md` whether at the root **or** under `.ai-factory/`; anything under `.ai-factory/specs/**`; anything under `docs/**`.
  - **Not selected:** the transient orchestrator artifacts — anything under `.ai-factory/plans/**`, `.ai-factory/plan-reviews/**`, `.ai-factory/reviews/**`, `.ai-factory/notes/**`, `.ai-factory/handoffs/**` — and code paths (e.g. `src/main.py`).
  This is the swappable per-project seam; only the default ai-factory profile ships now, and 5.1's `CodeSourceStrategy(SourceStrategy)` extends it later — so keep the base ABC free of any ai-factory-specific concept. Pure: no imports of `core`, `llm`, the store, or any I/O. Operates only on the `path` string passed in.

- [x] **Task 2: `chunk_markdown` stub + pinned oversize threshold**
  Files: `src/knowledge/chunker.py`
  Add a module-level pure function `chunk_markdown(text: str) -> list[str]` whose body is a raising stub (`raise NotImplementedError`). Document the intended contract in the docstring for 3.4.2 to implement: split a Markdown document on headings into **whole sections** (heading line + its body kept together as one chunk), so a retrieved chunk keeps its point rather than a fixed-window fragment; a section longer than the oversize threshold splits further on sub-headings / paragraph boundaries, **never mid-sentence**.
  Pin the "oversized" threshold explicitly rather than leaving it emergent from a test fixture: declare a named module constant `MAX_CHUNK_CHARS = 2000` (character-based — the chunker is pure and has no tokenizer; ~2000 chars sits comfortably under a typical embedding model's context and is a sane max-chunk boundary for 3.4.2 to adopt). The docstring states: a section whose length is `> MAX_CHUNK_CHARS` is oversized and must be split; a section `<= MAX_CHUNK_CHARS` stays a single chunk. Both the constant and the tests reference this one number so the constraint is stated, not discovered.
  Pure: no I/O, no dependency on other modules — operates only on the in-memory `text` argument.

### Phase 2: Red tests

- [x] **Task 3: Selection red tests** (depends on Task 1)
  Files: `tests/knowledge/test_source_strategy.py`
  New pure test module (no DB, no fixtures — do not request the `pg_pool`/`store`/`make_chunk` fixtures from `tests/knowledge/conftest.py`; they are opt-in, so pure tests collect and run without a database). Instantiate `AiFactorySourceStrategy` and pin `selects`. Use two parametrized cases (e.g. `pytest.mark.parametrize`) for clarity:
  - **Selected → `True`:** `CLAUDE.md`, `AGENTS.md`, `ARCHITECTURE.md`, `ROADMAP.md`, `.ai-factory/ARCHITECTURE.md`, `.ai-factory/ROADMAP.md`, `.ai-factory/specs/43-source-strategy-chunker-contract.md`, `docs/spec/understanding.md`, `docs/architecture.md`.
  - **Not selected → `False`:** `.ai-factory/plans/17-x.md`, `.ai-factory/plan-reviews/x.md`, `.ai-factory/reviews/x.md`, `.ai-factory/notes/01-x.md`, `.ai-factory/handoffs/x.md`, and code paths such as `src/main.py`, `src/knowledge/store.py`.
  Cover both the selected set and the excluded plan-noise/code set (the excluded set is the actual hazard — silent indexing of orchestrator plan-noise). Tests are red now because `selects` raises; 3.4.2 greens them.

- [x] **Task 4: Chunking red tests** (depends on Task 2)
  Files: `tests/knowledge/test_chunker.py`
  New pure test module (no DB/fixtures). Import `MAX_CHUNK_CHARS` from `src.knowledge.chunker` and size fixtures against it so the threshold is referenced, not re-guessed. Pin `chunk_markdown` behavior with in-memory Markdown strings:
  - **Section boundaries:** a multi-section document splits into one chunk per section, and each chunk contains its heading line together with that section's body (assert the count and that a heading and a distinctive body line land in the same chunk). To keep the per-section count unambiguous, the fixture starts **directly at the first `##` heading** — no `# H1` title and no preamble before the first heading — and each `##` section is under `MAX_CHUNK_CHARS` with **no nested sub-headings** (sub-headings are reserved for the oversized case), so exactly one chunk per `##` section is the only correct count.
  - **Oversized split never mid-sentence:** a single section whose body exceeds `MAX_CHUNK_CHARS` (build it near a realistic boundary — one `##` heading with body just over `MAX_CHUNK_CHARS`, composed of multiple sub-headings/paragraphs of complete sentences) splits into more than one chunk, and **no** chunk boundary falls inside a sentence — assert every produced chunk, stripped, ends at a sentence/paragraph boundary (terminal punctuation or is a heading), so a mid-sentence cut fails the test. Sizing the fixture just over `MAX_CHUNK_CHARS` (rather than an arbitrary small size) means the test both reliably triggers the split and pins the same sane threshold 3.4.2 will implement — no rework loop.
  Tests are red now because `chunk_markdown` raises; 3.4.2 greens them.
