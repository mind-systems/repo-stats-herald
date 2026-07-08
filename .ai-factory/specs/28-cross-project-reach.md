# 7.2 — Cross-project reach

**Phase:** 7 — The reasoner over both memories. Depends on 7.1 (the reasoner core) and Phase 6 (the project graph).

## Current state

After 7.1, `Reasoner.answer` reasons about one repo (or org-wide) in isolation from the project graph — a query about a project whose feature unblocks another project's work gets no mention of that ripple.

## Change

Extend the reasoner to fold in related-project context when a repo-scoped query has neighbors.

- `Reasoner.answer` (7.1), after assembling the queried repo's own context:
  - find related projects two ways: org-wide semantic retrieval (`KnowledgeStore.query(embedding, k, repo=None)`, taking the distinct repos of the results, excluding the queried repo) and `ProjectGraph.neighbors(repo)` (Phase 6);
  - for each neighbor found, retrieve its context (`KnowledgeStore.query(embedding, k, repo=neighbor)`) and fold it into the combined context passed to the prompt, framed as what it relates to / unblocks.
  - Only runs when `repo` is given — an org-wide query (`repo=None`) has no single project to find neighbors *of*.
- `ProjectGraph` added to `Reasoner`'s injected dependencies.

## Files & types

- edit `src/reasoning/reasoner.py` (`Reasoner` gains `ProjectGraph`, neighbor-folding in `answer`)

## Guards

- Uses `ProjectGraph` + `KnowledgeStore` **directly** — not the old `NeighborFinder` (spec 13, superseded), which was shaped around a resolved `LinkedChange`, not a free-text query. Cross-project reach is unified here, at this task — narration (8.1) reuses it directly, not a second mechanism.
- No surface heuristic — neighbors come from retrieval + the graph only, same discipline as `NeighborFinder`.
- A neighbor whose context retrieval fails is dropped from the answer, not fatal.
- **Failure isolation is scoped to the single failing neighbor** — a too-broad exception handler that swallows the primary repo's own context along with a failed neighbor's is exactly the bug this guard exists to prevent; only the failing neighbor is ever dropped.
- No neighbors found (neither retrieval nor graph) → the single-project answer from 7.1 stands unchanged.

## Verification

- A query about a project whose contract another repo consumes → the answer reasons about the consuming project too (what it unblocks there).
- A mocked failing neighbor (`KnowledgeStore.query` raises for exactly one neighbor) → the answer still succeeds, with the primary repo's own context **and** the other neighbors' context intact — only the failing neighbor is absent.
- A query about an isolated project (no edges, nothing retrieved) → the single-project answer, unchanged from 7.1.
- An org-wide query (`repo=None`) → neighbor-folding does not run; behavior matches 7.1.
