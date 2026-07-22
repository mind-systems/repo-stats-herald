## Plan Review Summary

**Plan:** 3.4.1 — Source strategy + chunker (red tests)
**Files Reviewed:** 1 plan + traced references (contract spec 43, ROADMAP 3.4.x line, `docs/architecture.md`, `docs/spec/understanding.md`, `src/knowledge/store.py`, `src/llm/{client,embedder}.py`, `tests/knowledge/conftest.py`, `pyproject.toml`)
**Risk Level:** 🟢 Low

### Context Gates
- **Architecture** (`.ai-factory/ARCHITECTURE.md`): PASS. New modules land in the `src/knowledge/` feature package; the plan mandates pure logic with no imports of `core`/`llm`/the store and no env reads — consistent with the "features depend on infra, never scatter, no env inside features" rules. Placement matches the CLAUDE.md module table and the 5.1 sibling (`code_source_strategy.py`) which also lives under `src/knowledge/`.
- **Rules** (`.ai-factory/RULES.md`): PASS. File is intentionally empty (no counter-defaults); nothing to violate.
- **Roadmap** (`.ai-factory/ROADMAP.md`): PASS. The plan maps cleanly to line 39 (`3.4.1 — Source strategy + chunker (red tests)`) and its `Spec:` tag (`43-source-strategy-chunker-contract.md`). The selected/excluded sets, the `selects(path)->bool` signature, the `chunk_markdown` "whole sections by heading / oversized never mid-sentence" contract, and the "stubs raise, tests red, 3.4.2 greens" framing all match both the ROADMAP line and the governing contract spec 43. `AGENTS.md` and `.ai-factory/specs/**` are correctly added beyond the `understanding.md` default-profile table, matching contract spec 43 §Change.

### Critical Issues
None. The plan is well-scoped, grounded in the actual codebase, and faithful to the governing contract.

Verified against ground truth:
- **ABC style** — `KnowledgeStore`, `LLMClient`, `Embedder` are all `abc.ABC` + `@abstractmethod`, plain class names, no `I` prefix. The plan's instruction to mirror this (and the co-located concrete subclass, as in `store.py`'s `PgVectorStore`) is correct for this project. The global "interface marker" default is correctly overridden by the observed project convention.
- **Stub goes red, not un-instantiable** — `AiFactorySourceStrategy` overrides the abstract `selects` with a raising body, so it instantiates and fails at the call site (red), which is the intent. Correct.
- **Fixture opt-in reasoning** — `tests/knowledge/conftest.py` fixtures (`pg_pool`/`store`/`make_chunk`) are function-scoped and only bind when requested by name; `asyncio_mode = "auto"`. Pure test modules that request none will collect and run with no database. The plan's claim holds.
- **Paths** — `src/knowledge/{source_strategy,chunker}.py` are new files in an existing package (`__init__.py` present); `tests/knowledge/` has `__init__.py`; the excluded-set example paths (`src/main.py`, `src/knowledge/store.py`) exist. No migration needed (pure logic, no schema touch) — correctly declared.

### Findings

**1. (Medium) Oversized-chunk split threshold is unpinned — the red fixture's size will silently become the binding constraint on 3.4.2's chunker.**
Task 4's oversized test asserts "an oversized single section splits into more than one chunk," but neither the plan nor contract spec 43 names a size threshold that makes a section "oversized." Because 3.4.2 must green this test *without re-deciding logic* and cannot edit the test, whatever fixture size Task 4 picks becomes the de-facto maximum-chunk threshold 3.4.2 is forced to adopt. If Task 4 builds a modest fixture and 3.4.2 later wants a larger, embedding-token-driven threshold (the natural real-world choice), the test stays red after a correct-looking implementation → a rework loop. This is fixable now, inside Task 4's boundary: instruct the author to size the oversized fixture at a *realistic* max-chunk boundary (roughly the intended split size, not an arbitrary small one), so the fixture both reliably triggers a split and pins a sane threshold for 3.4.2. Optionally, state that threshold as a number in the contract so the coupling is explicit rather than emergent.

**2. (Low) Section-boundary fixture should exclude pre-first-heading content and nested sub-headings so the per-section count is unambiguous.**
Task 4's normal test asserts an exact chunk count ("one chunk per section"). `chunk_markdown`'s behavior on a leading `# H1`/preamble before the first section, and on a `###` sub-heading nested inside an under-size `##` section, is not fixed by the contract. If the fixture contains either, the expected count is ambiguous and the test may pin an unintended behavior. The plan already says "several `##` headings each with body text" — make it explicit that the normal fixture starts directly at the first heading with no preamble and no nested sub-headings, reserving sub-headings for the oversized case.

### Positive Notes
- Selection contract is transcribed precisely from the governing spec, including the genuinely hazardous excluded set (orchestrator plan-noise) that the spec calls out as the silent-failure risk — and the tests are told to cover the excluded set explicitly.
- Correctly identifies this as pure, no-I/O, no-migration, no-logging, no-docs work and keeps the base ABC free of ai-factory-specific concepts so 5.1's `CodeSourceStrategy` can extend the seam.
- Task dependencies (Task 3→1, Task 4→2) and the red→green handoff to 3.4.2 are stated cleanly.
- Docstring-as-contract instruction gives 3.4.2 the selection/chunking rules at the implementation site without implementing them here — exactly the tests-first shape the milestone wants.

The two findings above are refinements to the test-authoring instructions, not structural defects; the plan's architecture, paths, API usage, and contract fidelity are sound.
