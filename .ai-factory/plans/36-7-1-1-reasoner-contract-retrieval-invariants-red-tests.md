# Plan: 7.1.1 — Reasoner contract + retrieval invariants (red tests)

## Context
Define the `Reasoner` feature's shape — a concrete class with a stubbed `answer(query, repo=None)` — and pin its four silent-failure retrieval invariants with red tests over mocked collaborators, ahead of 7.1.2's real implementation.

## Settings
- Testing: yes (red tests are the deliverable)
- Logging: none
- Docs: no

## Tasks

### Phase 1: Reasoner feature package

- [x] **Task 1: Create the `reasoning` feature package with a stubbed `Reasoner`**
  Files: `src/reasoning/__init__.py`, `src/reasoning/reasoner.py`
  Create a new feature package under `src/` following the feature-modular + constructor-DI convention (see `src/summarization/service.py` (class `Summarizer`) and `src/knowledge/code_distiller.py` for the shape). In `reasoner.py`:
  - Import the abstractions only: `Embedder` from `src/llm/embedder.py`, `LLMClient` from `src/llm/client.py`, `KnowledgeStore` from `src/knowledge/store.py`, `EpisodicStore` from `src/episodic/store.py`. Per the spec, `Reasoner` is a **concrete** class (the swap seam is the injected `LLMClient`) and names no concrete model/store.
  - `class Reasoner:` with `__init__(self, llm: LLMClient, embedder: Embedder, knowledge: KnowledgeStore, episodic: EpisodicStore) -> None` storing each collaborator on a private attribute. Wiring of concretes is out of scope here (belongs at a future composition root).
  - `async def answer(self, query: str, repo: str | None = None) -> str:` as a **stub** that raises `NotImplementedError`. Add a docstring capturing the intended shape from the spec (embed `query` **once** via `embed([query])[0]`; query both `KnowledgeStore.query(embedding, k, repo=…)` and `EpisodicStore.query(embedding, k, repo=…)` with that one embedding — episodic `since`/`until` left at their `None` defaults, no time window; scope to `repo` when given, else org-wide; `repo` is the bare `push.repo` name, never `org/repo`; assemble combined context; build a reasoning prompt; call `LLMClient.generate(prompt)`). Do **not** implement any of this logic — the stub raises so the Phase 2 tests are red. Note: `embed` and both stores' `query` are `async`, so `answer` is `async`.
  `k` is not fixed by the spec; the tests must not assert on its value (assert `repo` and the embedding vector only).

### Phase 2: Red tests over mocked collaborators

- [x] **Task 2: Test fixtures — fake/mocked collaborators** (depends on Task 1)
  Files: `tests/reasoning/__init__.py`, `tests/reasoning/conftest.py`
  Create the test package (mirror `tests/knowledge/`, `tests/episodic/`). The suite runs against **mocks only** — no real Postgres/pgvector, no real Ollama. `pyproject.toml` sets `asyncio_mode = "auto"`, so async tests need no decorator.
  Provide configurable fakes implementing the real ABCs (follow the `FakeLLMClient` pattern in `tests/knowledge/test_code_distiller_contract.py`), each recording its calls so tests can assert on arguments:
  - `Embedder` fake: `embed(texts)` records each call and returns one fixed sentinel vector (e.g. `[[0.1, 0.2, 0.3]]`) so tests can assert it was called exactly once and identify "the same embedding" downstream.
  - `KnowledgeStore` fake: `query(embedding, k, repo=None)` records `(embedding, k, repo)`; behavior (return a list of `Chunk`, return `[]`, or raise) is configurable per test.
  - `EpisodicStore` fake: `query(embedding, k, repo=None, since=None, until=None)` records its args; same configurable return/raise behavior with `EpisodicEntry` results. Implement the other abstract methods (`upsert`/`delete`, `append`/`recorded_commit_shas`) as trivial no-ops/raisers so the fakes are concrete.
  Add a `Reasoner` builder fixture wiring the fakes. Provide small helpers to build a `Chunk` (`src/knowledge/store.py`) and an `EpisodicEntry` (`src/episodic/models.py`) as store results.

- [x] **Task 3: Red test — one embedding, two stores** (depends on Task 2)
  Files: `tests/reasoning/test_reasoner_contract.py`
  Call `answer(query)`; assert the `Embedder.embed` fake was called **exactly once**, and that both `KnowledgeStore.query` and `EpisodicStore.query` received **that same embedding vector** (identity/equality of the recorded first-positional arg). Red because the stub raises.

- [x] **Task 4: Red test — `repo`-scoping** (depends on Task 2)
  Files: `tests/reasoning/test_reasoner_contract.py`
  Two cases: `answer(query, repo="api")` passes `repo="api"` (a **bare** name) to **both** stores' `query`; `answer(query)` passes `repo=None` to both. Assert on the recorded `repo` kwarg for each store — never silently defaulting a given repo to org-wide, or vice versa.

- [x] **Task 5: Red test — honest no-memory** (depends on Task 2)
  Files: `tests/reasoning/test_reasoner_contract.py`
  Configure both store fakes to return `[]`. Assert the outcome is distinguishable from the grounded path: either `answer` short-circuits without calling `LLMClient.generate` at all, or the prompt passed to `generate` carries an explicit no-memory marker/framing that a prompt built from non-empty results does not. Structure the assertion to accept either resolution (the spec permits both) — e.g. compare the no-memory case against a control case where a store returns results.

- [x] **Task 6: Red test — failure isolation** (depends on Task 2)
  Files: `tests/reasoning/test_reasoner_contract.py`
  Three cases: (a) `KnowledgeStore.query` raises, `EpisodicStore.query` returns results → `answer` returns a `str` built from the survivor, no exception propagates; (b) symmetric — episodic raises, knowledge survives; (c) both raise → the no-memory path is taken (returns a `str`, or short-circuits, consistent with Task 5). Assert no exception escapes `answer` in any case. Red because the stub raises `NotImplementedError`.
Note for all Phase 2 tasks: every test must fail **only** because `answer` raises `NotImplementedError` — never because of an import, fixture, or signature mismatch. 7.1.2 turns these green unchanged; do not encode implementation choices the spec leaves open (`k` value, exact prompt text, combined-context format).
