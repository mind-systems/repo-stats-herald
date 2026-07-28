# Plan: 7.2 — Cross-project reach

## Context
Extend `Reasoner` so a repo-scoped answer also folds in each related project's semantic context — neighbors discovered via org-wide retrieval unioned with the directed project graph — reusing 7.1's single embedding and `k`, inside the shared `_gather_context` helper that 8.1 inherits.

## Settings
- Testing: yes
- Logging: minimal
- Docs: no

## Tasks

### Phase 1: Neighbor context in the gathered model and prompt

- [x] **Task 1: Carry neighbor semantic context through `GatheredContext` and the reasoning prompt**
  Files: `src/reasoning/reasoner.py`, `src/reasoning/prompt.py`
  Add a `neighbor_chunks: list[Chunk]` field to the `GatheredContext` dataclass (`src/reasoning/reasoner.py`) — a flat list of neighbor-repo chunks, each already carrying its own `Chunk.repo` (semantic only; no episodic entries for neighbors). `GatheredContext` is `@dataclass(frozen=True)`, so the default must be `neighbor_chunks: list[Chunk] = field(default_factory=list)` — a literal `[]` raises `ValueError: mutable default ... is not allowed` at class-definition time. Add `field` to the `from dataclasses import dataclass` line.
  In `ReasoningPromptBuilder.build` (`src/reasoning/prompt.py`), add a `neighbor_chunks: list[Chunk] | None = None` parameter and render a new "related projects" section — framed as what the queried project **relates to / unblocks** — that groups the neighbor chunks by `Chunk.repo` (bare repo name, never `org/repo`). Follow the existing `_CHUNK_SECTION_HEADER` / `_render_chunk` pattern; add a `_NEIGHBOR_SECTION_HEADER` template. Include neighbor chunks in the emptiness check that selects `_NO_MEMORY_TEMPLATE`: the honest no-memory framing must fire only when primary chunks, entries, **and** neighbor chunks are all empty (so a primary-empty-but-neighbor-present answer is still grounded, not no-memory).

### Phase 2: Neighbor discovery and folding in the reasoner

- [x] **Task 2: Inject `ProjectGraph` and fold neighbor context inside `_gather_context`** (depends on Task 1)
  Files: `src/reasoning/reasoner.py`
  Add `graph: ProjectGraph` (import `from src.graph.store import ProjectGraph`) to `Reasoner.__init__`'s injected dependencies, stored as `self._graph`. Extend the existing `_gather_context(query, repo)` helper — **do not** add a parallel neighbor step in `answer` (8.1's `narrate` must inherit reach through this one helper).
  After the primary chunks/entries are gathered (unchanged 7.1 per-store try/except), and **only when `repo is not None`**, run neighbor folding reusing the single `embedding` already computed at the top of the helper — never re-embed:
  1. **Retrieval neighbors:** call `self._knowledge.query(embedding, self._k, repo=None)`; the neighbor ids are the **distinct `Chunk.repo`** values of the results, excluding the queried `repo` and excluding `None`. Wrap this discovery call in its own try/except so a failing org-wide query yields no retrieval neighbors without aborting the answer or losing graph neighbors.
  2. **Graph neighbors:** call `await self._graph.neighbors(repo)` (bare `to_repo`, directed/outgoing only — never symmetrized). Wrap in try/except so a graph failure yields no graph neighbors without losing retrieval neighbors or primary context.
  3. **Union + dedupe** the two id sets into one collection (order deterministic, e.g. retrieval order then graph order), each neighbor folded **once**, excluding the queried `repo`.
  4. For each neighbor id, call `self._knowledge.query(embedding, self._k, repo=neighbor)` (bare id passed verbatim — never `org/repo`-qualified or stripped) inside a **per-neighbor** try/except: a single neighbor whose retrieval raises is logged (`logger.warning`, minimal) and dropped, leaving the primary context and all other neighbors intact. Failure isolation must be scoped to the single failing neighbor — the handler must not wrap the primary gather or the whole neighbor loop.
  Collect all surviving neighbors' chunks into the flat `neighbor_chunks` list on the returned `GatheredContext`. Update `answer` to pass `gathered.neighbor_chunks` into `self._prompt.build(...)`. Reuse the **same `self._k`** — introduce no new retrieval-size constant. When `repo is None`, or no neighbors are found either way, `neighbor_chunks` stays empty and the answer matches 7.1 unchanged.

### Phase 3: Composition root and tests

- [x] **Task 3: Wire `ProjectGraph` at the eval composition root** (depends on Task 2)
  Files: `scripts/eval.py`
  Import `from src.graph.store import PgProjectGraph` and pass `graph=PgProjectGraph(pool)` into the `Reasoner(...)` construction in `_run()` (it already builds `pool` for the reasoner case). This is the only place `Reasoner` is currently constructed; `src/main.py` does not yet wire it.

- [x] **Task 4: Tests for neighbor folding** (depends on Task 2)
  Files: `tests/reasoning/conftest.py`, `tests/reasoning/test_cross_project_reach.py`
  In `conftest.py`:
  - Add a `FakeProjectGraph` implementing `ProjectGraph`. `ProjectGraph` declares **five** abstractmethods (`add_edge`, `edges_from`, `neighbors`, `remove_seed_edges`, `replace_seed_edges`) — a subclass overriding only `neighbors` cannot be instantiated, so stub all five (the non-exercised four as trivial `pass`/return, mirroring how `FakeKnowledgeStore`/`FakeEpisodicStore` already stub their unused abstract methods in the same file). `neighbors` records its calls and returns a preset `list[str]` or raises a preset error, **defaulting to an empty list** when unconfigured — so a test that never configures the graph gets a benign no-neighbors run. Add a `fake_graph` fixture and update the `reasoner` fixture to inject it.
  - **Extend `FakeKnowledgeStore` for per-`repo` control.** Its current single `result`/`error` apply to every `query` regardless of `repo`, which cannot express the per-neighbor scenarios (point 4 needs primary OK + one neighbor raising + another neighbor OK; points 1/2 need discovery `repo=None` and each per-neighbor `query(repo=…)` to return distinct chunk sets). Add `results: dict[str | None, list[Chunk]]` and `errors: dict[str | None, Exception]` keyed by the `repo` argument, consulted first and **falling back to the existing single `result`/`error`** when a key is absent — so the 7.1.1 contract tests (which set only the single fields) stay green unchanged. `query` still appends to `calls`.
  - Ensure the existing 7.1.1 contract tests stay green. Note the two distinct cases:
    - `test_answer_embeds_once_and_shares_embedding_with_both_stores` calls `answer` with `repo=None`, so neighbor folding does not run — its `len(fake_knowledge.calls) == 1` single-knowledge-call invariant holds unchanged.
    - `test_repo_scoping_passes_bare_repo_to_both_stores` calls `answer(..., repo="api")`, so folding **does** run (org-wide discovery + `graph.neighbors("api")` fire after the primary gather). It survives because it asserts only on `calls[0]` — the primary `repo="api"` query, issued **before** discovery. Two things keep it green and must hold: Task 2's ordering (primary knowledge/episodic queries precede neighbor discovery, so `calls[0]` stays the primary call — do not let discovery precede the primary query), and the unconfigured fakes' benign defaults (`FakeProjectGraph.neighbors` → `[]`, `FakeKnowledgeStore`'s `repo=None` discovery falling back to the empty single `result`), so the folding loop over `repo="api"` issues no spurious per-neighbor queries and does not raise.
  Add `test_cross_project_reach.py` covering the spec's verification points over the fakes: (1) a repo-scoped query with a graph neighbor and/or a retrieval-surfaced distinct `Chunk.repo` → that neighbor's `query(repo=<bare id>)` is issued and its chunks reach the prompt, framed as related; (2) a neighbor surfaced by **both** org-wide retrieval and `neighbors(repo)` is folded **once** and queried with the **bare** id (assert the store never receives an `org/repo` form); (3) exactly one `Embedder.embed` call across the whole `answer` despite the neighbor fan-out; (4) one neighbor's `knowledge.query` raising → the answer still succeeds with primary context and the other neighbors intact, only the failing neighbor absent; (5) `repo=None` → neighbor folding does not run (no org-wide discovery call, behavior matches 7.1); (6) no neighbors (empty graph, nothing distinct retrieved) → single-project answer unchanged.
