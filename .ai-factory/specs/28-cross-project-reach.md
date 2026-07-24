# 7.2 — Cross-project reach

**Phase:** 7 — The reasoner over both memories. Depends on 7.1 (the reasoner core) and Phase 6 (the project graph).

## Current state

After 7.1, `Reasoner.answer` reasons about one repo (or org-wide) in isolation from the project graph — a query about a project whose feature unblocks another project's work gets no mention of that ripple.

## Change

Extend the reasoner to fold in related-project context when a repo-scoped query has neighbors.

- `Reasoner.answer` (7.1), after assembling the queried repo's own context, **reusing the single query embedding 7.1 already computed** (7.1's "one embedding per `answer`" invariant, spec `48` — 7.2 never re-embeds):
  - find related projects two ways and **union them, deduplicated**: org-wide semantic retrieval (`KnowledgeStore.query(embedding, k, repo=None)` — the neighbor ids are the **distinct `Chunk.repo`** values of the results (`Chunk.repo`, `src/knowledge/store.py`), excluding the queried repo) and `ProjectGraph.neighbors(repo)` (Phase 6 — `list[str]` of bare `to_repo`, outgoing edges only, `src/graph/store.py`);
  - for each neighbor in that unioned set, retrieve its context (`KnowledgeStore.query(embedding, k, repo=neighbor)` — **semantic only; `EpisodicStore` is not queried for a neighbor**, unlike the primary repo which gets both stores in 7.1) and fold it into the combined context passed to the prompt, framed as what it relates to / unblocks;
  - reuse the **same retrieval `k`** 7.1's primary retrieval uses — 7.2 introduces no new retrieval-size constant, and the neighbor count is naturally bounded (at most `k` distinct retrieved repos plus the outgoing graph degree).
  - Only runs when `repo` is given — an org-wide query (`repo=None`) has no single project to find neighbors *of*.
- `ProjectGraph` added to `Reasoner`'s injected dependencies.

## Files & types

- edit `src/reasoning/reasoner.py` (`Reasoner` gains `ProjectGraph`, neighbor-folding in `answer`)

## Guards

- Uses `ProjectGraph` + `KnowledgeStore` **directly** — not the old `NeighborFinder` (spec 13, superseded), which was shaped around a resolved `LinkedChange`, not a free-text query. Cross-project reach is unified here, at this task — narration (8.1) reuses it directly, not a second mechanism.
- **Neighbor folding lives inside 7.1.2's shared `_gather_context(query, repo)` helper**, not inlined into `answer`'s prompt path — so `narrate` (8.1) inherits cross-project reach through the same retrieval path, not a second copy. This task extends the helper; it does not add a parallel neighbor step in `answer`.
- No surface heuristic — neighbors come from retrieval + the graph only, same discipline as `NeighborFinder`.
- A neighbor whose context retrieval fails is dropped from the answer, not fatal.
- **Failure isolation is scoped to the single failing neighbor** — a too-broad exception handler that swallows the primary repo's own context along with a failed neighbor's is exactly the bug this guard exists to prevent; only the failing neighbor is ever dropped.
- No neighbors found (neither retrieval nor graph) → the single-project answer from 7.1 stands unchanged.
- **Repo identity is the bare `push.repo` name everywhere — never `org/repo`.** `answer`'s `repo` argument, the neighbor ids from `neighbors(repo)` (bare `to_repo`, `src/graph/store.py`), the `Chunk.repo` of retrieval results, and every `KnowledgeStore.query(repo=…)` scope all use the one key the stores and the graph already share (`Edge.to_repo` and `Chunk.repo` are bare, `src/graph/models.py` / `src/knowledge/store.py`). A neighbor id resolves against the same identity a push carries; do not org-qualify or strip.
- **`neighbors(repo)` is directed** — outgoing edges only (`repo -> to`), never symmetrized. Reach follows declared/seeded direction; 7.2 adds no reverse-edge expansion.

## Verification

- A query about a project whose contract another repo consumes → the answer reasons about the consuming project too (what it unblocks there).
- A mocked failing neighbor (`KnowledgeStore.query` raises for exactly one neighbor) → the answer still succeeds, with the primary repo's own context **and** the other neighbors' context intact — only the failing neighbor is absent.
- A query about an isolated project (no edges, nothing retrieved) → the single-project answer, unchanged from 7.1.
- An org-wide query (`repo=None`) → neighbor-folding does not run; behavior matches 7.1.
- A repo surfaced by **both** org-wide retrieval and `neighbors(repo)` is folded **once** (union deduped), and its context query is issued with `repo=` the bare name — a mocked store asserts it receives the bare id, never an `org/repo` form.
- `Embedder.embed` is called **once** across the whole `answer` — the org-wide discovery query and every per-neighbor query reuse that one vector (extends 7.1's one-embedding invariant through the neighbor fan-out).
