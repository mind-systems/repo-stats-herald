# 6.2 — Forest narration

> SUPERSEDED by task 8.1 (spec 30) — narration is now a reasoner projection.

**Phase:** 6 — Cross-project narration. Depends on 6.1 (the neighbors) and Phase 5 (the narrator). Closes the phase: a change is narrated in ecosystem terms.

## Current state

After 6.1, Herald can find the projects a change relates to. Phase 5's `ChangelogNarrator` narrates the changed project in isolation. Nothing weaves the neighbors into the note — Herald cannot yet say what a change unblocks elsewhere.

## Change

Extend the narrator to frame a change across projects when neighbors are found.

- `ChangelogNarrator.narrate` (from 5.2) calls `NeighborFinder.find(change)`:
  - **neighbors found** — for each neighbor, retrieve its relevant context (`KnowledgeStore.query(embedding, k, repo=neighbor.repo)`), and build the prompt to narrate the ripple: the feature that advanced and its project, then the work it unblocks in the dependent projects. The output stays feature-level (what it unblocks), not code.
  - **no neighbors** — the single-project note from Phase 5 stands unchanged.
- The extension is in the narrator's prompt assembly; delivery of the note to channels is Phase 7.

## Files & types

- edit `src/changelog/narrator.py` (`ChangelogNarrator` consults `NeighborFinder`, adds neighbor context to the prompt)

## Guards

- The ripple is feature-level — the feature that advanced and what it unblocks — never a code-level or contract-mechanics description.
- Bounded to the neighbors 6.1 returned; Herald does not walk the whole graph.
- Single-project fallback intact: no neighbors → exactly Phase 5's note.
- A neighbor whose context retrieval fails is dropped from the ripple, not fatal.

## Verification

- A change to a contract a neighbor consumes → prose naming the feature that advanced in its project and the neighbor it unblocks.
- An isolated change → the single-project note, unchanged.
- The note reads at the level of features and direction, not diffs.
