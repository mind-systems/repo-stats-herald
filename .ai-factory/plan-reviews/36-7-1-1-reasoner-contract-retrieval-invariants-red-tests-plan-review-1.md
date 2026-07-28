## Plan Review Summary

**Plan:** 7.1.1 — Reasoner contract + retrieval invariants (red tests)
**Artifacts reviewed:** plan + governing spec (`.ai-factory/specs/48-reasoner-contract.md`), roadmap line 7.1.1/7.1.2, and every collaborator the plan targets (`src/llm/embedder.py`, `src/llm/client.py`, `src/knowledge/store.py`, `src/episodic/store.py`, `src/episodic/models.py`, `tests/knowledge/test_code_distiller_contract.py`, `tests/{knowledge,episodic}/conftest.py`, `pyproject.toml`)
**Risk Level:** 🟢 Low

### Context Gates
- **Architecture** (`.ai-factory/ARCHITECTURE.md`): PASS. The new `src/reasoning/` package follows the feature-modular + constructor-DI pattern. `Reasoner` depends only on infra (`llm/`) and the public ABCs of other features (`KnowledgeStore`, `EpisodicStore`), injected via constructor — the exact shape the dependency rules require (§Dependency Rules, lines 41–43). Wiring of concretes is correctly deferred to a future composition root. Note: the ARCHITECTURE template suggests `service.py` for a feature's logic file, but the codebase already uses domain-specific names (`store.py`, `code_distiller.py`, `collector.py`), and the governing spec explicitly pins `src/reasoning/reasoner.py` — the plan matches the spec, so no violation.
- **Rules** (`.ai-factory/RULES.md`): PASS. File is intentionally empty (no project counter-defaults).
- **Roadmap** (`.ai-factory/ROADMAP.md`): PASS. Plan maps cleanly to line 77 (7.1.1) and its `Spec:` tag. The four invariants, the concrete-class decision, the bare-`push.repo` key, and the "stub raises → tests red" discipline all match the roadmap contract and the spec.

### Correctness verification against ground truth
Every API the plan relies on was checked against the actual code:
- `Embedder.embed(texts: list[str]) -> list[list[float]]` is a batch API (`src/llm/embedder.py`) — plan's `embed([query])[0]` is correct.
- `KnowledgeStore.query(embedding, k, repo=None)` (`src/knowledge/store.py`) — signature matches.
- `EpisodicStore.query(embedding, k, repo=None, since=None, until=None)` (`src/episodic/store.py`) — signature matches; plan correctly leaves `since`/`until` at their `None` defaults (no time window).
- `LLMClient.generate(prompt: str) -> str` (`src/llm/client.py`) — matches.
- `Chunk` lives in `src/knowledge/store.py`, `EpisodicEntry` in `src/episodic/models.py` — the test-helper source paths in Task 2 are correct.
- EpisodicStore fake must implement `append` + `recorded_commit_shas` (plus `query`); KnowledgeStore fake must implement `upsert` + `delete` (plus `query`). Task 2's list of "other abstract methods" enumerates exactly the right set to keep both fakes concrete.
- `pyproject.toml` line 22 sets `asyncio_mode = "auto"` — Task 2's claim that async tests need no decorator is verified.
- `FakeLLMClient` recording pattern in `tests/knowledge/test_code_distiller_contract.py` exists as cited; `make_entry`/`make_chunk` builder-fixture precedent exists in the episodic/knowledge conftests, so Task 2's helper design is grounded.

The test design is sound: the sentinel-vector Embedder fake makes the "same embedding" identity assertion (Task 3) trivially checkable; the control-case framing for honest-no-memory (Task 5) correctly accepts either resolution the spec permits (short-circuit **or** distinct prompt marker); the failure-isolation cases (Task 6) cover both asymmetric survivals and the both-raise → no-memory path. The "assert `repo` and the embedding only, never `k`" guard (Task 1 + Phase-2 note) correctly avoids encoding a choice 7.1.2 owns.

### Critical Issues
None. No missing steps, no wrong API assumptions, no missing migrations (this task adds no schema — the stores it queries already own their `schema.sql`), no security surface (mocks only, no network, no DB).

### Minor Issues
1. **Incorrect example file path** — Task 1 (line 17) points at `src/summarization/summarizer.py` "for the shape," but that file does not exist; the summarizer lives in `src/summarization/service.py` (class `Summarizer`). An implementer opening the pointer hits a missing file. The parallel reference `src/knowledge/code_distiller.py` is correct and sufficient, so this won't derail the work, but the path should read `src/summarization/service.py`.
2. **Stray code fence around the closing note** — the "Note for all Phase 2 tasks" (lines 49–51) is wrapped in an unlabeled ``` … ``` fence with no matching opener above it, so the guidance renders as a code block instead of prose. Cosmetic; drop the fence so the note reads as instruction text.

### Positive Notes
- The plan faithfully carries the spec's four silent-failure invariants down to per-task red tests, one invariant per task, exactly as the spec's Verification section requires.
- It correctly holds the line on scope: `answer` is a pure stub raising `NotImplementedError`, all logic deferred to 7.1.2, and the Phase-2 note explicitly forbids encoding open choices (`k`, prompt text, context format) — so 7.1.2 can green these tests "unchanged," matching the roadmap contract.
- The "import abstractions only, name no concrete model/store" instruction directly enforces the spec's DI guard and the architecture's dependency rules.
- Task dependencies (Task 2 → Tasks 3–6, Task 1 → Task 2) are explicit and correct.

The two issues above are trivial and confined to the plan text, but they are real inaccuracies in the artifact, so this review does not pass clean.
