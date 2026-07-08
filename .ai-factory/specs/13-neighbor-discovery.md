# 6.1 — Neighbor discovery

> SUPERSEDED by the reasoner's cross-project reach (7.2) — narration finds neighbours through the reasoner.

**Phase:** 6 — Cross-project narration. First task. Finds the projects a change relates to, without a surface heuristic.

## Current state

Phase 5's narrator scopes its retrieval to the changed repo (`KnowledgeStore.query(..., repo=change.repo)`) — it narrates one project in isolation. The knowledge store (Phase 3) holds every served project's knowledge and its `query` accepts `repo=None` (org-wide); the project graph (Phase 4) holds cross-project edges. Nothing yet combines them to find which other projects a change touches.

## Change

Add a finder that surfaces related projects from org-wide retrieval and the project graph — declared links come back through retrieval, undeclared ones through the graph.

- `src/changelog/neighbors.py`:
  - `Neighbor` (immutable): `repo: str`, `via: str` (`retrieved` | `edge`).
  - `NeighborFinder.find(change: LinkedChange) -> list[Neighbor]`:
    - **retrieved** — embed the change (its completed tasks / commit text) via the `Embedder`, `KnowledgeStore.query(embedding, k, repo=None)` (org-wide), and take the **distinct repos** of the returned chunks, excluding `change.repo`.
    - **edges** — `ProjectGraph.neighbors(change.repo)` (Phase 4).
    - union the two into `Neighbor`s (a repo found both ways keeps one entry; `via` records how it surfaced).
- Assembled at the composition root from the injected embedder, store, and graph.

## Files & types

- new `src/changelog/neighbors.py` (`Neighbor`, `NeighborFinder`)

## Guards

- Neighbors come from **retrieval + the graph only** — no "is this a contract surface" heuristic to guess at.
- `change.repo` is never its own neighbor.
- An empty result is valid — the change is single-project (Phase 5's note stands).
- Retrieval failure degrades to graph-only neighbors, never a crash.

## Verification

- A change to a contract another repo consumes surfaces that repo — via retrieval (its docs mention the contract) and/or a graph edge.
- A change unrelated to any other project → no neighbors.
- A repo reachable both by retrieval and by a configured edge appears once.
