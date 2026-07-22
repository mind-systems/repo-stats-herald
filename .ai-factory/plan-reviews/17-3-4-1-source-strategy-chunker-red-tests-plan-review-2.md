## Plan Review Summary

**Plan:** 3.4.1 — Source strategy + chunker (red tests)
**Files Reviewed:** 1 plan + traced references (contract spec `43-source-strategy-chunker-contract.md`, ROADMAP lines 39/40/59, `src/knowledge/store.py`, `src/llm/{client,embedder}.py`, `tests/knowledge/conftest.py`, `pyproject.toml`, `.ai-factory/ARCHITECTURE.md`, `.ai-factory/RULES.md`)
**Risk Level:** 🟢 Low

### Context Gates
- **Architecture** (`.ai-factory/ARCHITECTURE.md`): PASS. Both new modules land inside the existing `src/knowledge/` feature package. The plan mandates pure logic with no imports of `core`/`llm`/the store and no env reads — consistent with the composition-root/DI rules (concretes wired only at the root; features depend on abstractions, never read env). No cross-feature dependency introduced; the base ABC is kept free of ai-factory-specific concepts so 5.1's `CodeSourceStrategy` can extend the seam.
- **Rules** (`.ai-factory/RULES.md`): PASS. File is intentionally empty (no counter-defaults); nothing to violate.
- **Roadmap** (`.ai-factory/ROADMAP.md`): PASS. The plan maps cleanly to line 39 (`3.4.1 — Source strategy + chunker (red tests)`) and its `Spec:` tag (`43-source-strategy-chunker-contract.md`). The `selects(path) -> bool` signature, the selected/excluded sets, the `chunk_markdown` "whole sections by heading / oversized never mid-sentence" contract, and the "stubs raise, tests red, 3.4.2 greens" framing all match the ROADMAP line and the governing contract spec 43. `AGENTS.md` and `.ai-factory/specs/**` are correctly carried through from spec 43 §Change. The `CodeSourceStrategy(SourceStrategy)` forward-reference matches line 59 (5.1).
- **Skill-context** (`.ai-factory/skill-context/aif-review/SKILL.md`): absent — no project overrides to apply.

### Critical Issues
None. The plan is well-scoped, grounded in the actual codebase, and faithful to the governing contract.

Verified against ground truth:
- **ABC style** — `KnowledgeStore` (`src/knowledge/store.py`), `LLMClient` (`src/llm/client.py`), `Embedder` (`src/llm/embedder.py`) are all `abc.ABC` + `@abstractmethod`, plain class names, no `I` prefix, with a concrete subclass co-located (`PgVectorStore`). The plan's instruction to mirror this style (and to name the concrete `AiFactorySourceStrategy(SourceStrategy)`) is correct; the global interface-marker default is legitimately overridden by the observed project convention, and the concrete profile is a class, not an interface, so no marker applies.
- **Stub goes red, not un-instantiable** — `AiFactorySourceStrategy` overrides the abstract `selects` with a `raise NotImplementedError` body, so it instantiates and fails at the call site (red), which is the tests-first intent. Same for the module-level `chunk_markdown` stub. Correct.
- **Fixture opt-in reasoning** — `tests/knowledge/conftest.py` fixtures (`pg_pool`/`store`/`make_chunk`) are function-scoped and bind only when requested by name; `pyproject.toml` sets `asyncio_mode = "auto"` and `testpaths = ["tests"]`. Pure test modules that request none will collect and run with no database. The plan's claim holds.
- **Paths** — `src/knowledge/{source_strategy,chunker}.py` are new files in an existing package; `tests/knowledge/__init__.py` exists (0 bytes) so `test_source_strategy.py`/`test_chunker.py` collect. Every excluded-set example path used in the tests is real or plausibly-shaped (`src/main.py`, `src/knowledge/store.py` exist; `.ai-factory/specs/43-...md` exists). No migration needed — pure logic, no schema touch — correctly declared.

### Prior-review findings — disposition
Both findings from plan-review-1 are already resolved in this revision:
1. **Unpinned oversize threshold (Medium)** — closed. Task 2 now declares a named module constant `MAX_CHUNK_CHARS = 2000`, states the `> / <=` split rule against it, and Task 4 imports it and sizes the oversized fixture "just over `MAX_CHUNK_CHARS`," so the threshold is stated by both the code and the tests rather than emerging from an arbitrary fixture size. This removes the 3.4.2 rework-loop risk.
2. **Ambiguous section-boundary count (Low)** — closed. Task 4's normal fixture is now specified to start "directly at the first `##` heading — no `# H1` title and no preamble," with each `##` section under `MAX_CHUNK_CHARS` and "no nested sub-headings" (reserved for the oversized case), making one-chunk-per-section the only correct count.

### Positive Notes
- Selection contract is transcribed precisely from governing spec 43, including the genuinely hazardous excluded set (orchestrator plan-noise) the spec names as the silent-failure risk, and the tests are told to cover the excluded set explicitly.
- Correctly identifies the work as pure, no-I/O, no-migration, no-logging, no-docs and keeps the base ABC free of ai-factory-specific concepts so 5.1's `CodeSourceStrategy` extends the seam cleanly.
- Threshold is pinned once (`MAX_CHUNK_CHARS`) and referenced by both constant and tests — the constraint is stated, not discovered.
- Task dependencies (Task 3→1, Task 4→2) and the red→green handoff to 3.4.2 are stated cleanly; docstring-as-contract gives 3.4.2 the rules at the implementation site without implementing them here.

The plan's architecture, paths, API usage, and contract fidelity are sound, and the two earlier refinements are folded in.

PLAN_REVIEW_PASS
