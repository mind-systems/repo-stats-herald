## Plan Review Summary

**Plan:** 3.4.2 — Artifact indexer (impl)
**Files Reviewed:** plan + targeted codebase (`source_strategy.py`, `chunker.py`, `store.py`, `llm/embedder.py`, `github/mirror.py`, both red-test files, spec 07/43, ROADMAP)
**Risk Level:** 🟢 Low

### Context Gates
- **Architecture** (`.ai-factory/ARCHITECTURE.md`): WARN-free. `ArtifactIndexer` lives in the `knowledge` feature and depends only on infra (`llm/embedder.py`) and same-feature modules (`store.py`, `source_strategy.py`, `chunker.py`) — no feature→feature import. Constructor DI of the three abstractions with concretes wired only at the composition root is respected; the plan explicitly defers wiring to 3.6. Aligned.
- **Rules** (`.ai-factory/RULES.md`): file is intentionally empty (no counter-defaults). Nothing to enforce.
- **Roadmap**: ROADMAP.md line 40 (`3.4.2 — Artifact indexer (impl)`) matches the plan title and scope; `Spec: .ai-factory/specs/07-source-strategy-indexer.md`. Governing spec 07 and the upstream contract spec 43 (3.4.1) both agree with the plan's selection set, chunking rule, and read→chunk→embed→upsert path. Linkage present and correct.
- **Skill-context** (`.ai-factory/skill-context/aif-review/SKILL.md`): absent — no project overrides to apply.

### Critical Issues
None.

### Verification against ground truth

- **Selection logic (Task 1)** matches every case in `tests/knowledge/test_source_strategy.py`: root `CLAUDE.md`/`AGENTS.md`, `ARCHITECTURE.md`/`ROADMAP.md` at root or `.ai-factory/<name>`, `.ai-factory/specs/` prefix, `docs/` prefix → selected; plans/plan-reviews/reviews/notes/handoffs and `src/**` → not selected. The plan's "bare filename vs `.ai-factory/<name>`" phrasing correctly excludes deeper `.ai-factory/` artifacts. Docstring-accuracy instruction is present.
- **Chunker (Task 2)** satisfies both red tests: whole-section-per-heading (3 `##` sections → 3 chunks with heading+body kept together) and oversized-section split with `_ends_at_boundary` honored (split on sub-headings, then paragraphs, never mid-sentence). The generated `OVERSIZED_SECTION` splits cleanly on `###` sub-headings (each piece ≈300 chars, well under `MAX_CHUNK_CHARS=2000`, ending in `.`), so the plan's strategy greens the test.
- **API usage (Task 3)** is correct: `Chunk` is defined in `src.knowledge.store` (import path as stated); `Embedder` in `src/llm/embedder.py`; `KnowledgeStore.upsert(repo, path, items)` / `delete(repo, path)` signatures match. `RepoMirror.tree(...)` in `src/github/mirror.py` is a context manager yielding the worktree `Path`, so `tree / path` read is sound and the "caller holds it open" assumption is accurate.
- **Empty-chunk idempotency** reasoning is correct end-to-end: `chunk_markdown("")` → `[]`, `Embedder.embed([])` returns `[]` (guard at `embedder.py:25`), zip yields no items, and `PgVectorStore.upsert` still runs the `DELETE` in its transaction, clearing stale chunks. The plan's instruction not to special-case-away the empty path is right.
- **`Chunk` defaults**: leaving `repo`/`path`/`chunk_index` at `None` is correct — `upsert` assigns `repo`/`path` from its args and `chunk_index` from `enumerate`, ignoring the value-object fields.
- **No migration needed**: the `chunks` schema shipped in 3.3; this task adds no schema.

### Positive Notes
- The plan correctly reuses `selects` and `chunk_markdown` rather than re-deriving selection/chunking in the indexer, matching spec 07's guard.
- Trust-boundary discipline is explicit: the indexer only touches the handed-in tree path, never the mirror internals or the network.
- Idempotency-via-upsert and the select-skip no-op are both called out with their rationale.

## Deferred observations
- Affects: indexer verification (integration / 3.6 wiring) — Task 3 ships `ArtifactIndexer` under `Testing: no`. The greened red tests (3.4.1) cover only the pure `selects`/`chunk_markdown` surfaces; the indexer's own orchestration (embed↔chunk order-aligned zip, upsert invocation) has no automated test, and spec 07's verification bullets (`index` populates queryable chunks; `remove` clears them) require a live mirror+store. This is consistent with the milestone's tests-first split and the deliberate `Testing: no` setting, so it is not a finding for this task — but whoever owns the 3.6 wiring / integration pass should ensure the read→chunk→embed→upsert path is exercised against a real store before the indexer is relied upon.

PLAN_REVIEW_PASS
