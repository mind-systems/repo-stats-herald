# 10.1.2 — Report sections: summary, per-branch, remaining (impl)

**Phase:** 10 — Reporting engine (composable reports). Depends on 10.1.1 (the section seam + composition), 4.2 (resolver), 8.1 (`Reasoner.narrate`), Phase 3 (mirror). Greens the composition with three real content blocks.

## Current state

10.1.1 defines `ReportSection`/`Report` with stubbed sections and red composition tests. No section produces real content yet. The summary and "remaining" are two distinct units of meaning and must be separate sections (a release wants the summary, not "what's still open").

## Change

Implement three sections; each is a self-contained content block over the report's resolved `(before, after)` range.

- `SummarySection(ReportSection)` — the **holistic shipped story**: resolve the aggregate change (`LinkedChange.resolve` over the `(before, after)` range on the mirror) and narrate it with `Reasoner.narrate(change, lang)` (8.1) — what **advanced** and what it **unblocks** (cross-project reach, 7.2). Empty window → `None`. It does **not** read open tasks.
- `PerBranchSection(ReportSection)` — the **per-branch** block: enumerate branches with commits in the `(before, after)` range, and for each resolve its change and narrate who-did-what (`Reasoner.narrate`); one labelled sub-part per branch; none active → `None`.
- `RemainingSection(ReportSection)` — the **what-remains** block: read the currently-open `[ ]` tasks at HEAD (via the source strategy's roadmap path) and frame them; no open tasks → `None`.
- **`narrate_report` is retired.** With `open_tasks` gone from `SummarySection`, its only differentiator from 8.1's `narrate(change, lang)` disappears — sections call `narrate` directly. (Editor: confirm `open_tasks` was the sole difference before deleting; if `RemainingSection` needs LLM framing, any residual primitive lives ONLY there, never as a second summary sibling.)
- Sections register under keys `summary`, `per_branch`, `remaining`.

## Files & types

- edit `src/reasoning/reasoner.py` — retire `narrate_report`; sections use `Reasoner.narrate` (8.1)
- new `src/changelog/sections/summary.py`, `.../per_branch.py`, `.../remaining.py`

## Guards

- Reads the mirror (change) and the roadmap-at-HEAD (remaining) only; feature-level, not a raw commit list.
- `changelog` imports from `reasoning`, never the reverse.
- No separate `NeighborFinder`/narrator path — cross-project "unblocks" comes from the reasoner's reach (7.2).
- **Mandatory tests (mocked mirror/`git log`, mocked source strategy, mocked reasoner):**
  - `PerBranchSection` — inactive branch skipped; N active → N sub-parts; none → `None`.
  - `RemainingSection` — exact `[ ]`-line read at HEAD (never `[x]`, never retrieval); no open tasks → `None`.
  - `SummarySection` — empty window → `None` before any LLM call; does not read open tasks.
- LLM prose quality → the eval harness against a user-authored reference, not unit tests.

## Verification

- A window on two branches → `PerBranchSection` a part per branch; `SummarySection` one holistic narration; `RemainingSection` the open tasks.
- Empty window + no open tasks → all three `None` → report `None`.
- Prose diffs against references through the eval harness.
