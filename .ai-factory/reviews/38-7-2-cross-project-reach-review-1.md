## Code Review — 7.2 Cross-project reach

**Files reviewed (in full):** `src/reasoning/reasoner.py`, `src/reasoning/prompt.py`, `scripts/eval.py`, `tests/reasoning/conftest.py`, `tests/reasoning/test_cross_project_reach.py`, against ground truth — `src/graph/store.py`, `src/graph/models.py`, `src/knowledge/store.py`, `src/episodic/store.py`, `tests/reasoning/test_reasoner_contract.py` — plus the plan and governing spec `28-cross-project-reach.md`.
**Risk level:** 🟢 Low
**Tests:** full suite `92 passed` (reasoning subset `14 passed`).

### What the change does
Extends `Reasoner._gather_context` to fold neighbor semantic context into a repo-scoped answer: after the primary gather, and only when `repo is not None`, it discovers neighbors two ways (org-wide `knowledge.query(repo=None)` → distinct `Chunk.repo`, unioned with `graph.neighbors(repo)`), deduped, then folds each neighbor's `knowledge.query(repo=neighbor)` chunks (semantic only) into a new `GatheredContext.neighbor_chunks`, rendered as a "relates to / unblocks" prompt section. `ProjectGraph` is injected and wired at the eval composition root.

### Correctness verification
- **Failure isolation (spec's sharpest guard, line 30):** three separately-scoped `try/except` blocks — org-wide discovery, `graph.neighbors`, and a per-neighbor handler inside the loop — all inside `if repo is not None` and all *after* the primary chunks/entries are gathered (`reasoner.py:69–79` before `:81–116`). A failing neighbor or a failing discovery method can never drop the primary context or the other neighbors. Confirmed by `test_one_failing_neighbor_is_dropped_without_losing_primary_or_other_neighbors`.
- **Dedup + self-exclusion:** `seen_neighbors` folds each neighbor exactly once across both paths; both loops exclude the queried `repo`, and the retrieval loop also excludes `hit.repo is None` (`Chunk.repo` is `str | None`). The primary repo is never re-queried as a neighbor, so no duplicate primary content. Confirmed by `test_neighbor_from_both_discovery_paths_is_folded_once_with_bare_id`.
- **One-embedding invariant:** a single `embed([query])` at `reasoner.py:67` is reused for the primary queries, org-wide discovery, and every per-neighbor query — no re-embed in the fan-out. Confirmed by `test_single_embed_call_despite_neighbor_fan_out`.
- **Same `k`, no new constant:** every `query` uses `self._k`. ✓
- **Bare identity end to end:** `repo`, `neighbors` `to_repo`, `Chunk.repo`, and every `query(repo=…)` pass bare names verbatim — no `org/repo` qualify/strip. Asserted by the both-paths test (`"/" not in repo_arg`).
- **`repo=None` short-circuit:** neighbor folding is skipped entirely; the 7.1 org-wide path is byte-for-byte unchanged (no graph call, single knowledge call). Confirmed by `test_no_repo_scope_skips_neighbor_folding_entirely`.
- **Semantic-only neighbors:** `EpisodicStore` is never queried per neighbor. ✓
- **Prompt emptiness:** `ReasoningPromptBuilder.build` folds `neighbor_chunks` into the no-memory decision (`prompt.py:41`), so a primary-empty-but-neighbor-present answer stays grounded rather than falling to the no-memory template. The neighbor section groups by `Chunk.repo` in deterministic insertion order.
- **No-regression on the folding-exercising contract test:** `test_repo_scoping_passes_bare_repo_to_both_stores` runs folding for `repo="api"` yet stays green because the primary queries precede discovery (so `calls[0]` is the primary call) and the unconfigured fakes default benignly (`FakeProjectGraph.neighbors → []`, `FakeKnowledgeStore` `repo=None` falls back to the empty single `result`).

### Runtime / integration checks
- **Frozen dataclass default:** `neighbor_chunks: list[Chunk] = field(default_factory=list)` with `field` imported — no mutable-default error at class definition.
- **Composition root:** `PgProjectGraph(pool)` imported and passed into the only production construction site (`scripts/eval.py`); `src/main.py` does not yet wire `Reasoner`. The new required `graph` parameter is supplied at both construction sites (eval + conftest fixture).
- **No schema/migration needed:** `project_edges` and `chunks` already exist (Phases 6/3); the change adds no DDL.
- **`FakeProjectGraph`** stubs all five `ProjectGraph` abstractmethods, so it is instantiable.

### Findings
None. The implementation matches the plan and spec, all invariants and guards are exercised by tests, and the full suite passes with no regression.

REVIEW_PASS
