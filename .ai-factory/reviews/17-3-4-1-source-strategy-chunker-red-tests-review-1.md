## Code Review — 3.4.1 Source strategy + chunker (red tests)

**Scope reviewed:** `git diff HEAD` + `git status`. Code changes: `src/knowledge/source_strategy.py`, `src/knowledge/chunker.py`, `tests/knowledge/test_source_strategy.py`, `tests/knowledge/test_chunker.py`. (Plan / plan-review / sidecar JSON are orchestrator artifacts, not code — noted but not reviewed for defects.)

**Task shape:** This is a **tests-first (red)** task. The deliverable is: two pure modules whose bodies are raising stubs, plus unit tests that pin the future contract and therefore fail now. 3.4.2 greens them. Correctness here means: stubs raise, tests are red *for the right reason* (the stub, not a collection/import/logic bug), and the pinned contract is satisfiable by a spec-conformant 3.4.2 without a rework loop.

### Verification performed
- `uv run pytest tests/knowledge/test_chunker.py tests/knowledge/test_source_strategy.py` → **18 failed, 0 collection errors**. Every failure traces to `raise NotImplementedError` in the stub under test — the intended red state.
- Both chunker tests fail *inside* `chunk_markdown(...)` on the stub; the oversized test's pre-assertion `len(OVERSIZED_SECTION) > MAX_CHUNK_CHARS` passes first (fixture is 2155 chars vs. 2000), so the test exercises the real path.
- Confirmed the oversized fixture builder terminates and starts at a `## ` heading; no infinite-loop or preamble ambiguity.

### Correctness notes (no defects)
- **Stubs** — `SourceStrategy` (ABC + `@abstractmethod`) with co-located concrete `AiFactorySourceStrategy` overriding `selects` with a raising body; `chunk_markdown` a module-level raising stub with `MAX_CHUNK_CHARS = 2000`. Mirrors the project's `KnowledgeStore`/`PgVectorStore` ABC style. Pure — no `core`/`llm`/store imports, no I/O.
- **Tests collect without a database** — neither test module requests the `pg_pool`/`store`/`make_chunk` fixtures from `tests/knowledge/conftest.py` (function-scoped, opt-in), so they run with no Postgres, matching the "pure, no I/O" guard.
- **Selection tests** cover both the selected set and the hazardous excluded set (orchestrator plan-noise + code) the spec names as the silent-failure risk.
- **Satisfiability (no rework trap)** — Test 1 pins one chunk per `##` section for a 3-section, sub-heading-free, sub-threshold doc: consistent with contract spec 43's "whole sections by heading". Test 2's `_ends_at_boundary` accepts a chunk whose last non-blank line is a heading *or* ends in `.`/`!`/`?`; a sub-heading/paragraph splitter satisfies this, so a correct 3.4.2 can go green. Threshold is pinned once (`MAX_CHUNK_CHARS`) and referenced by both the stub docstring and the fixture — the plan-review-1 emergent-threshold finding is closed in the code.
- `assert strategy.selects(path) is True/False` uses identity comparison — a deliberate, defensible strictness that pins a real `bool` return (guards a future truthy-non-bool implementation), consistent with the `-> bool` signature.

### Security
No attack surface: pure in-memory logic, no I/O, no network, no secrets, no external input handling.

No findings.

REVIEW_PASS
