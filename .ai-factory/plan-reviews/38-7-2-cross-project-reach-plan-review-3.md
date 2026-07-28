## Code Review Summary

**Files Reviewed:** plan `38-7-2-cross-project-reach.md` against ground truth — `src/reasoning/reasoner.py`, `src/reasoning/prompt.py`, `src/graph/store.py`, `src/graph/models.py`, `src/knowledge/store.py`, `scripts/eval.py`, `src/core/config.py`, `tests/reasoning/conftest.py`, `tests/reasoning/test_reasoner_contract.py` — plus the governing spec `.ai-factory/specs/28-cross-project-reach.md`, roadmap line 7.2, and the two prior plan reviews.
**Risk Level:** 🟢 Low

### Context Gates
- **Architecture (`.ai-factory/ARCHITECTURE.md`):** PASS. Injecting `ProjectGraph` (graph's public ABC, `src/graph/store.py:8`) into `Reasoner`'s constructor and wiring the concrete `PgProjectGraph` only at the eval composition root matches the dependency rules — a feature depends on another feature's public class, injected; concretes are chosen only at a composition root. Identical shape to the already-injected `KnowledgeStore`/`EpisodicStore`. No feature-internal import.
- **Rules (`.ai-factory/RULES.md`):** PASS — file carries no counter-defaults.
- **Roadmap (line 7.2) + governing spec (`28-cross-project-reach.md`):** PASS on intent. Every spec verification point (lines 37–42) has a matching Task-4 test (points 1–6), and every ground-truth interface the plan names checks out:
  - `KnowledgeStore.query(embedding, k, repo=None) -> list[Chunk]` with hydrated `Chunk.repo` (`src/knowledge/store.py:35,91`); `repo=None` is the org-wide branch (`store.py:70`).
  - `ProjectGraph.neighbors(repo) -> list[str]`, directed outgoing `to_repo` only (`src/graph/store.py:24,86`).
  - `ProjectGraph` declares exactly five abstractmethods — `add_edge`, `edges_from`, `neighbors`, `remove_seed_edges`, `replace_seed_edges` (`store.py:9–36`).
  - `PgProjectGraph(pool)` takes the asyncpg pool `scripts/eval.py:168` already builds for the reasoner case.
  - `self._k` is `Settings.reasoner_k` (default `8`, `src/core/config.py:33`).
  - No schema/migration introduced or needed — `project_edges` and `chunks` already exist from Phases 6/3.

### Prior-review follow-through
Both prior reviews' findings are fully folded into this revision:
- **Review-1 / F2 — `GatheredContext.neighbor_chunks` default:** Task 1 now pins `field(default_factory=list)` and adding `field` to the `from dataclasses import dataclass` line, matching the `@dataclass(frozen=True)` at `reasoner.py:14`. Correct — a literal `[]` would raise at class-definition time.
- **Review-1 / F1 — `FakeKnowledgeStore` per-`repo` control:** Task 4 now specifies `results: dict[str | None, list[Chunk]]` and `errors: dict[str | None, Exception]` keyed by the `repo` argument, consulted first and **falling back** to the existing single `result`/`error`. This keeps the 7.1.1 contract tests (which set only the single fields, `test_reasoner_contract.py:57–58,86–87`) green while enabling the per-neighbor scenarios (point 4).
- **Review-1 / F3 — all five abstractmethods stubbed:** Task 4 now calls out that `FakeProjectGraph` must stub all five, since overriding only `neighbors` leaves the class abstract and non-instantiable.
- **Review-2 / F1 — contract-test reasoning:** Task 4 now separates the two cases correctly — `test_answer_embeds_once_and_shares_embedding_with_both_stores` (`repo=None`, no folding, carries the `len(calls)==1` invariant) vs. `test_repo_scoping_passes_bare_repo_to_both_stores` (`repo="api"`, folding **does** run, survives because it asserts only on `calls[0]`, the primary call issued before discovery). The load-bearing ordering (primary queries precede discovery) and the pinned benign defaults (`FakeProjectGraph.neighbors` → `[]`, `FakeKnowledgeStore` `repo=None` fallback → empty) are both named.

### Critical Issues
None. The approach is architecturally sound, spec-faithful, and every factual claim about the codebase verified against ground truth.

### Positive Notes
- **Failure isolation** is specified to the spec's sharpest guard (spec line 30): three separately-scoped try/excepts — org-wide discovery, `graph.neighbors`, and a **per-neighbor** handler inside the loop — so a single failing neighbor is dropped without swallowing the primary gather or the rest of the loop.
- **Bare-identity discipline** is threaded end to end (answer's `repo`, `neighbors`' bare `to_repo`, `Chunk.repo`, every `query(repo=…)`), matching the spec's identity guard; Task 4 point (2) asserts the store never receives an `org/repo` form.
- Both the queried `repo` **and** `None` are excluded from the distinct-`Chunk.repo` retrieval-neighbor set — `Chunk.repo` is `str | None` (`store.py:11`), so the `None` exclusion is a real, easily-missed guard the plan calls out.
- **Folding lives in the shared `_gather_context` helper** with an explicit "do not add a parallel step in `answer`" instruction, preserving the 8.1 `narrate` inheritance the spec and roadmap require.
- One-embedding invariant preserved and explicitly tested (point 3): the embedding computed once at the top of the helper is reused for discovery and every per-neighbor query.
- Reuses `self._k` with no new retrieval-size constant, as the spec mandates; the `repo is None` short-circuit keeps the 7.1 org-wide path unchanged.
- Semantic-only for neighbors (no episodic query per neighbor) matches spec line 15; the prompt emptiness check correctly folds `neighbor_chunks` into the no-memory decision so a primary-empty-but-neighbor-present answer stays grounded.
- Composition-root analysis is accurate: `Reasoner` is constructed only in `scripts/eval.py` and the conftest fixture (grep-confirmed); `src/main.py` does not yet wire it. Task 4 updates the fixture in lockstep with Task 2's new `graph` dependency, so the required parameter breaks nothing.

The plan is a faithful, ground-truth-accurate decomposition of spec `28-cross-project-reach.md`. All findings from both prior rounds are closed, and this pass surfaces no new issues.

PLAN_REVIEW_PASS
