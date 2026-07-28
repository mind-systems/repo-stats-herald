## Plan Review Summary

**Plan:** `.ai-factory/plans/65-artifactindexer.md` — Test Plan: ArtifactIndexer
**Governing spec:** `.ai-factory/specs/74-artifact-indexer-test-plan.md` (via ROADMAP_TESTS.md line 15 "ArtifactIndexer")
**Risk Level:** 🟢 Low

### Context Gates
- **Roadmap (ROADMAP_TESTS.md):** WARN-free. The task line resolves cleanly — `# Test Plan: ArtifactIndexer` maps to the "ArtifactIndexer" test-coverage entry, whose `Spec:` is `74-artifact-indexer-test-plan.md`. The plan's own "from spec 74" and "spec 07 exemplars" references both point at real, correct files (`.ai-factory/specs/74-...md`, `.ai-factory/specs/07-source-strategy-indexer.md`). Note: the plan *file* number 65 is the orchestrator's plan sequence index and is unrelated to spec `65-collector-failure-signal-contract.md` — not a defect, just worth flagging that the two "65"s are different artifacts.
- **Architecture (ARCHITECTURE.md):** No boundary concerns. This is a DB-free unit suite under `tests/knowledge/`, testing orchestration of injected abstractions — consistent with the feature-modular, constructor-DI pattern.
- **Rules / skill-context:** No `.ai-factory/skill-context/aif-review/SKILL.md` present; RULES.md carries no test-specific conventions that bear on this plan.

### Verification against ground truth

Every technical assumption in the plan was checked against the actual source and holds:

- **`src/knowledge/indexer.py`** — the plan's description of the flow (gate on `strategy.selects(path)` → `(tree/path).read_text("utf-8")` catching only `UnicodeDecodeError` → `chunk_markdown` → single `embedder.embed(chunks)` → `zip(..., strict=True)` → `Chunk(content, embedding)` → `store.upsert(repo, path, items)`; `remove` → unconditional `store.delete`) matches the code line-for-line.
- **`SourceStrategy`** — only `selects` is abstract; `roadmap_paths` has a default. `FakeSourceStrategy` implementing only `selects` is correct.
- **`Embedder.embed(texts) -> list[list[float]]`** — signature matches; the `embed([])` tolerance the plan mandates is genuinely exercised (empty-file case calls `embed([])`).
- **`KnowledgeStore`** — three abstract methods (`upsert`, `delete`, `query`); the fake must implement all three. Correct.
- **`Chunk`** — frozen dataclass `Chunk(content, embedding, repo=None, path=None, chunk_index=None)`; the indexer leaves `chunk_index=None`, so the plan's "pin list order, not the field" instruction (Task 2, Gotchas) is right and avoids a vacuous `== None` assertion.
- **`chunk_markdown`** — `chunk_markdown("")` and whitespace-only both return `[]` (blank sections filtered), validating the empty-file case's `upsert == [(repo, path, [])]`.
- **`AiFactorySourceStrategy` exemplars** — verified against `selects`: `CLAUDE.md`, `.ai-factory/ARCHITECTURE.md`, `.ai-factory/specs/03-x.md` are selected; `.ai-factory/plan-reviews/01-x.md`, `.ai-factory/handoffs/02-x.md`, `src/main.py` are not. The plan's parametrized expectations are accurate.
- **Test isolation** — `tests/knowledge/conftest.py` `pg_pool`/`store` open a real Postgres pool; the plan's insistence on building fakes in-file and not requesting them is correct. `make_chunk` there is pure and DB-free, matching the plan's "safe" note.
- **`tests/reasoning/conftest.py`** — its `FakeEmbedder` does return one `SENTINEL_VECTOR` for every text; the plan's warning against reusing it (it would hide reorder/off-by-one bugs) is well-founded.
- **`asyncio_mode = "auto"`** confirmed in `pyproject.toml` — plain `async def test_*` with no marker is correct.

**Spec coverage:** all 21 spec test cases are present and correctly grouped — cases 1–5 → Task 1, 6–8 → Task 2, 9–11 → Task 3, 12–13 → Task 4, 14–18 → Task 5, 19–21 → Task 6. Every gotcha from the spec is carried into the plan's Gotchas section.

### Critical Issues
None. No missing steps, no wrong codebase assumptions, no incorrect file paths or API usage. No migrations are relevant (test-only plan) and there is no security surface.

### Positive Notes
- The plan correctly reproduces the spec's central hazard framing (the selection gate as the silent-failure point) and keeps assertions on collaborator calls rather than `caplog`.
- Position-distinct fake vectors are mandated up front, which is exactly what makes the pairing/ordering cases (Task 2) non-vacuous.
- Scope discipline is explicit and correct: selection rules, chunk boundaries, and store semantics are deferred to their existing suites; only orchestration is pinned here.

PLAN_REVIEW_PASS
