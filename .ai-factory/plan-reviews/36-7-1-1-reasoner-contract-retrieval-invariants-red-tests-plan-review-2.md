## Plan Review Summary

**Plan:** 7.1.1 — Reasoner contract + retrieval invariants (red tests)
**Artifacts reviewed:** plan + governing spec (`.ai-factory/specs/48-reasoner-contract.md`), round-1 review, and every collaborator the plan targets (`src/llm/embedder.py`, `src/llm/client.py`, `src/knowledge/store.py`, `src/episodic/store.py`, `src/episodic/models.py`, `src/summarization/service.py`, `tests/knowledge/test_code_distiller_contract.py`, `tests/{knowledge,episodic}/conftest.py`, `pyproject.toml`)
**Risk Level:** 🟢 Low

### Round-1 issues — both fixed
1. **Example path corrected.** Task 1 (line 17) now reads `src/summarization/service.py` (class `Summarizer`) — verified to exist with that class. The previous dangling reference to `src/summarization/summarizer.py` is gone.
2. **Stray code fence removed.** The "Note for all Phase 2 tasks" (line 49) now renders as prose; no unmatched ``` fence remains.

### Context Gates
- **Architecture** (`.ai-factory/ARCHITECTURE.md`): PASS. The new `src/reasoning/` package follows feature-modular + constructor-DI: `Reasoner` depends only on infra (`llm/`) and the public ABCs of sibling features (`KnowledgeStore`, `EpisodicStore`), injected via constructor. Wiring of concretes is correctly deferred to a future composition root, matching the pattern in `src/summarization/service.py`. The spec pins the file name `src/reasoning/reasoner.py`, so the domain-specific filename (over the template's `service.py`) is intentional and consistent with existing packages (`store.py`, `code_distiller.py`, `collector.py`).
- **Rules** (`.ai-factory/RULES.md`): PASS. File is intentionally empty (no project counter-defaults).
- **Roadmap / Spec** (`.ai-factory/specs/48-reasoner-contract.md`): PASS. The plan carries the spec's four silent-failure invariants (one embedding/two stores, `repo`-scoping, honest no-memory, failure isolation) down to one red test per invariant (Tasks 3–6), the concrete-class + injected-`LLMClient`-seam decision, the bare-`push.repo` key, and the "stub raises → tests red, 7.1.2 turns green unchanged" discipline. All match. (The spec's own prose says "three retrieval-construction invariants" in one sentence but then lists and verifies four — an internal spec wording glitch; the plan correctly implements four, so this is not a plan defect.)

### Correctness verification against ground truth
Every API the plan relies on re-checked against the actual code:
- `Embedder.embed(texts: list[str]) -> list[list[float]]` is a batch API (`src/llm/embedder.py`) — plan's `embed([query])[0]` is correct.
- `KnowledgeStore.query(embedding, k, repo=None)` (`src/knowledge/store.py`) — signature matches; abstract methods are `upsert`, `delete`, `query`, so Task 2's fake correctly must implement `upsert`/`delete` alongside `query`.
- `EpisodicStore.query(embedding, k, repo=None, since=None, until=None)` (`src/episodic/store.py`) — matches; plan correctly leaves `since`/`until` at their `None` defaults (no time window). Abstract methods are `append`, `query`, `recorded_commit_shas`, so Task 2's fake correctly must implement `append`/`recorded_commit_shas` alongside `query`.
- `LLMClient.generate(prompt: str) -> str` (`src/llm/client.py`) — matches.
- `Chunk` lives in `src/knowledge/store.py`, `EpisodicEntry` in `src/episodic/models.py` — Task 2's helper source paths are correct; both dataclasses are constructible from the fields the helpers would supply (`Chunk(content, embedding, …)`; `EpisodicEntry(repo, org_id, completed_tasks, commit_shas, content, embedding, changed_at)`).
- Test-package scaffolding: `tests/knowledge/__init__.py` and `tests/episodic/__init__.py` exist, so Task 2's `tests/reasoning/__init__.py` mirrors the precedent.
- `pyproject.toml` sets `asyncio_mode = "auto"` (line 22), `pythonpath = ["."]`, `testpaths = ["tests"]` — Task 2's "async tests need no decorator" is verified.
- The `FakeLLMClient` recording pattern (`tests/knowledge/test_code_distiller_contract.py`) is a real precedent; that file also demonstrates the exact red-test shape the plan reuses (call the stub, assert on the result, no try/except — the `NotImplementedError` makes the test red), so Tasks 3–6 are grounded.

The test design is sound: the fixed-sentinel Embedder fake makes the "same embedding" identity assertion (Task 3) trivially checkable; the control-case framing for honest-no-memory (Task 5) correctly accepts either resolution the spec permits (short-circuit **or** distinct prompt marker); the failure-isolation cases (Task 6) cover both asymmetric survivals and the both-raise → no-memory path. The "assert `repo` and the embedding only, never `k`" guard (Task 1 + Phase-2 note) correctly avoids encoding a choice 7.1.2 owns, and the closing note forbids encoding any other open choice (prompt text, combined-context format).

### Critical Issues
None. No missing steps, no wrong API assumptions, no missing migrations (this task adds no schema — the stores it queries already own their `schema.sql`), no security surface (mocks only, no network, no DB).

### Positive Notes
- One invariant → one red test, exactly as the spec's Verification section requires; task dependencies (Task 1 → Task 2 → Tasks 3–6) are explicit and correct.
- Scope is held tightly: `answer` is a pure stub raising `NotImplementedError`, all logic deferred to 7.1.2, and the plan repeatedly forbids encoding choices 7.1.2 owns — so 7.1.2 can turn these green "unchanged," matching the contract.
- "Import abstractions only, name no concrete model/store" directly enforces the spec's DI guard and the architecture's dependency rules.

Both round-1 issues are resolved and every API assumption re-verified against ground truth. Nothing to flag.

PLAN_REVIEW_PASS
