# 3.4.1 — Source strategy + chunker (red tests)

**Phase:** 3 — Repo mirror & semantic memory. Depends on nothing beyond Phase 1 (pure logic, no I/O). First half of the indexer milestone — the selection/chunking contract, pinned with red tests, ahead of the indexer implementation (3.4.2). The shared seam 5.1 (code source strategy) later extends.

## Current state

Nothing decides **which** files in a repo define the project (the source strategy — see `docs/architecture.md`), or splits a document into meaningful units. A wrong include/exclude rule doesn't crash — it silently indexes orchestrator plan-noise (`.ai-factory/plan-reviews/**`) into "what the project is now," or silently drops a governing artifact (`ROADMAP.md`) from the base, poisoning retrieval with no exception raised. A wrong chunk boundary is the same shape of hazard: a section split mid-thought reads as a plausible but wrong retrieval unit.

## Change

Define the `SourceStrategy` seam and the markdown chunker as pure, I/O-free logic, and pin their behavior with red tests before wiring them into the indexer.

- `src/knowledge/source_strategy.py` — `SourceStrategy`: `selects(path: str) -> bool`, deciding which files define a project. The **default ai-factory profile** matches the ai-factory layout, where the governing artifacts live under `.ai-factory/`, not the repo root. It selects `CLAUDE.md` and `AGENTS.md` (root), `ARCHITECTURE.md` and `ROADMAP.md` **whether at the root or under `.ai-factory/`**, the spec notes under `.ai-factory/specs/**`, and anything under `docs/**`. It leaves out the transient artifacts an orchestrator writes in passing — `.ai-factory/plans`, `.ai-factory/plan-reviews`, `.ai-factory/reviews`, `.ai-factory/notes`, `.ai-factory/handoffs` — and (for now) the code. This is the one place per-project variation lives; it is a swappable seam (only the default profile ships now; 5.1's `CodeSourceStrategy` extends it later).
- `src/knowledge/chunker.py` — `chunk_markdown(text: str) -> list[str]`: split on Markdown headings into **whole sections** (heading + body as one unit), so a retrieved chunk keeps its point rather than a fixed-window fragment. Oversized sections split on sub-headings/paragraphs, never mid-sentence.
- Write red tests pinning:
  - selection — `CLAUDE.md`/`AGENTS.md`/`ARCHITECTURE.md`/`ROADMAP.md` (root or `.ai-factory/`), `.ai-factory/specs/**`, `docs/**` → selected; `.ai-factory/plans/**`, `.ai-factory/plan-reviews/**`, `.ai-factory/reviews/**`, `.ai-factory/notes/**`, `.ai-factory/handoffs/**`, and code paths (e.g. `src/main.py`) → not selected;
  - chunking — a multi-section document splits along its headings, each chunk keeps heading+body together; an oversized section splits on sub-headings/paragraphs, never mid-sentence.

## Files & types

- new `src/knowledge/source_strategy.py` (`SourceStrategy`), `src/knowledge/chunker.py` (`chunk_markdown`)
- new test file(s) covering selection and chunking, pure (no fixtures beyond in-memory text/paths)

## Guards

- **Pure, no I/O** — this task reads no mirror, touches no database; `selects`/`chunk_markdown` operate on paths/text already in hand, so the red tests run without a mirror or store.
- The **source strategy is first-class and swappable** — the per-project "what defines this project" lives here, not scattered in the indexer; only the default ai-factory profile ships now.
- Tests-first: 3.4.2 wires these into the indexer, it does not re-decide selection/chunking logic.

## Verification

- The test suite added here is red only where the logic doesn't exist yet — pure unit tests, no I/O setup required, so once implemented they pass without a mirror or database.
- Selection tests cover both the selected set and the excluded set (plan-noise, code).
- Chunking tests cover a normal multi-section document and an oversized single section.
