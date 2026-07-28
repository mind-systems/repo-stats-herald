## Code Review Summary

**Files Reviewed:** plan `38-7-2-cross-project-reach.md` against ground truth — `src/reasoning/reasoner.py`, `src/reasoning/prompt.py`, `src/graph/store.py`, `src/knowledge/store.py`, `scripts/eval.py`, `src/core/config.py`, `tests/reasoning/conftest.py`, `tests/reasoning/test_reasoner_contract.py` — plus the governing spec `.ai-factory/specs/28-cross-project-reach.md` and roadmap line 7.2.
**Risk Level:** 🟢 Low

### Context Gates
- **Architecture (`.ai-factory/ARCHITECTURE.md`):** PASS. Injecting `ProjectGraph` (a public ABC) into `Reasoner`'s constructor and wiring the concrete `PgProjectGraph` only at the eval composition root matches the dependency rules — features depend on another feature's public class, injected; concretes chosen only at the composition root. Identical shape to the already-injected `KnowledgeStore`/`EpisodicStore`. No feature-internal import.
- **Rules (`.ai-factory/RULES.md`):** PASS (no counter-defaults apply).
- **Roadmap (line 7.2) + governing spec (`28-cross-project-reach.md`):** PASS on intent. Every spec verification point (lines 37–42) has a matching Task-4 test, and every ground-truth interface the plan names checks out: `KnowledgeStore.query(embedding, k, repo=None) -> list[Chunk]` with hydrated `Chunk.repo` (`src/knowledge/store.py:35,91`); `ProjectGraph.neighbors(repo) -> list[str]` directed outgoing `to_repo` only (`src/graph/store.py:24,86`); `ProjectGraph` declares exactly five abstractmethods (`add_edge`, `edges_from`, `neighbors`, `remove_seed_edges`, `replace_seed_edges`); `PgProjectGraph(pool)` takes the asyncpg pool `scripts/eval.py:168` already builds for the reasoner case; `self._k` is `Settings.reasoner_k` (`src/core/config.py:33`). No schema/migration is introduced or needed — `project_edges` and `chunks` already exist from Phases 6/3.

### Review-1 follow-through
All three findings from plan-review-1 are correctly folded into this revision:
- **`GatheredContext.neighbor_chunks`** now specifies `field(default_factory=list)` and adding `field` to the `from dataclasses import` line (Task 1) — matching the `@dataclass(frozen=True)` at `src/reasoning/reasoner.py:14`.
- **`FakeKnowledgeStore` per-`repo` control** is now an explicit Task-4 step (`results`/`errors` dicts keyed by `repo`, falling back to the single `result`/`error`).
- **All five `ProjectGraph` abstractmethods stubbed** in `FakeProjectGraph` is now called out explicitly (Task 4).

### Critical Issues
None. The approach is architecturally sound and spec-faithful.

### Findings

**1. (Low) Task 4's justification for the contract tests staying green rests on a wrong reading of the codebase, and the real green-ness depends on an unpinned fixture default.**
Task 4 states: *"Ensure the existing 7.1.1 contract tests stay green (they call `answer` with `repo=None`, so neighbor folding does not run …)."* That premise is false for one of them: `tests/reasoning/test_reasoner_contract.py::test_repo_scoping_passes_bare_repo_to_both_stores` (line 33) calls `await reasoner.answer("what changed?", repo="api")` — a **repo-scoped** call, so under Task 2 neighbor folding **does** run for it (org-wide discovery `query(repo=None)` + `graph.neighbors("api")` fire after the primary gather).

The test happens to survive — it asserts only on `fake_knowledge.calls[0][2]`/`fake_episodic.calls[0][2]` (the **first**, primary call), not on call count — but only because two things hold that the plan's stated reasoning glosses over:
- The primary knowledge/episodic queries are issued **before** neighbor discovery (Task 2 orders them "after the primary chunks/entries are gathered", so `calls[0]` stays the primary `repo="api"` call). Keep that ordering; do not let discovery precede the primary query.
- The `reasoner` fixture is now injected with `fake_graph`, whose `neighbors` for this un-configured test must return an **empty list by default** (and `FakeKnowledgeStore`'s `repo=None` discovery must fall back to the empty single `result`), or the folding loop over `repo="api"` would issue spurious per-neighbor queries or raise. Task 4 says `neighbors` "returns a preset `list[str]` or raises a preset error" but does not pin the **default** to `[]`; pin it, so a test that never configures the graph gets a benign no-neighbors run.

Fix within Task 4's own text: correct the parenthetical to acknowledge that `test_repo_scoping_passes_bare_repo_to_both_stores` exercises folding and survives because it asserts on the first (primary) call — while `test_answer_embeds_once_and_shares_embedding_with_both_stores` (line 16, genuinely `repo=None`) is the one carrying the `len(calls) == 1` single-knowledge-call invariant — and pin `FakeProjectGraph.neighbors`'s default return to an empty list. Contract tests do stay green when implemented per Task 2's ordering; the plan's *reason* just needs to match ground truth so the implementer keeps the load-bearing ordering and fixture default rather than trusting a "folding does not run here" that isn't true.

### Positive Notes
- Failure isolation is specified exactly to the spec's sharpest guard (spec line 30): three separately-scoped try/excepts — org-wide discovery, `graph.neighbors`, and a **per-neighbor** handler inside the loop — so a single failing neighbor is dropped without swallowing the primary gather or the rest of the loop.
- Both the queried `repo` **and** `None` are excluded from the distinct-`Chunk.repo` retrieval-neighbor set — `Chunk.repo` is `str | None` (`src/knowledge/store.py:11`), so the `None` exclusion is a real, easily-missed guard the plan calls out.
- Bare-identity discipline is threaded end to end (answer's `repo`, `neighbors`' bare `to_repo`, `Chunk.repo`, every `query(repo=…)`), matching the spec's identity guard; Task 4 point (2) asserts the store never receives an `org/repo` form.
- Folding lives in the shared `_gather_context` helper with an explicit "do not add a parallel step in `answer`" instruction, preserving the 8.1 `narrate` inheritance the spec and roadmap require.
- One-embedding invariant preserved and explicitly tested (point 3): the embedding computed once at the top of the helper is reused for discovery and every per-neighbor query.
- Reuses `self._k` with no new retrieval-size constant, as the spec mandates; the `repo is None` short-circuit keeps the 7.1 org-wide path unchanged.
- Composition-root analysis is accurate: `Reasoner` is constructed only in `scripts/eval.py` (`src/main.py` does not yet wire it), and Task 4 updates the conftest fixture in lockstep with Task 2's new required `graph` parameter.

Finding 1 is a Low-severity accuracy fix inside the plan's own file boundary (Task 4 wording + one fixture default); the design is correct as written.
