## Code Review Summary

**Files Reviewed:** plan `38-7-2-cross-project-reach.md` against `src/reasoning/reasoner.py`, `src/reasoning/prompt.py`, `src/graph/store.py`, `src/knowledge/store.py`, `scripts/eval.py`, `tests/reasoning/conftest.py`, governing spec `28-cross-project-reach.md`, and roadmap line 7.2.
**Risk Level:** 🟡 Medium

### Context Gates
- **Architecture (`.ai-factory/ARCHITECTURE.md`):** PASS. Injecting `ProjectGraph` (a public ABC) into `Reasoner` via the constructor and wiring the concrete `PgProjectGraph` only at the eval composition root matches the dependency rules (features depend on another feature's public class, injected; concretes chosen only at the composition root). It is the same shape already used for `KnowledgeStore`/`EpisodicStore`. No feature-internal import.
- **Rules (`.ai-factory/RULES.md`):** PASS (file is intentionally empty — no counter-defaults).
- **Roadmap (`.ai-factory/ROADMAP.md` line 7.2):** PASS. The plan is a faithful decomposition of the contract line and its `Spec:` target `28-cross-project-reach.md` — union+dedupe of retrieval and directed graph neighbors, single embedding reused, same `k`, semantic-only for neighbors, folding inside `_gather_context`, per-neighbor failure isolation, bare-name identity, `repo=None` skips folding. Every spec verification point (37–42) has a matching test in Task 4.
- **Governing spec (`28-cross-project-reach.md`):** PASS on intent. Ground-truth interfaces all check out: `KnowledgeStore.query(embedding, k, repo=None)` returns `list[Chunk]` with hydrated `Chunk.repo` (`src/knowledge/store.py`); `ProjectGraph.neighbors(repo) -> list[str]` is directed outgoing `to_repo` only (`src/graph/store.py`); `PgProjectGraph(pool)` takes the asyncpg pool `scripts/eval.py` already builds for the reasoner case. No schema/migration is introduced or needed (`project_edges` and `chunks` already exist from Phases 6/3).

### Critical Issues
None that block the approach. Two substantive gaps and one minor item to close before implementation.

### Findings

**1. (Medium) Task 4 test fakes cannot express the per-neighbor scenarios the plan requires.**
`tests/reasoning/conftest.py::FakeKnowledgeStore` has a *single* `result` list and a *single* `error` that apply to **every** `query` call regardless of the `repo` argument. Task 4's verification points cannot be built on that fake as-is:
- Point (4) — "one neighbor's `knowledge.query` raising → the answer still succeeds with primary context and the other neighbors intact, only the failing neighbor absent." With a single `error`, the primary query and the org-wide discovery query raise too, so the scenario (primary OK, neighbor n1 raises, neighbor n2 OK) is unrepresentable.
- Points (1)/(2) — distinguishing a retrieval-surfaced neighbor from a graph neighbor, and asserting a both-surfaced neighbor's chunks reach the prompt, is muddy when discovery (`repo=None`) and every per-neighbor `query(repo=…)` return the identical `result`.

Task 4 only calls out adding `FakeProjectGraph` and updating the `reasoner` fixture; it is silent on the knowledge-store fake. The plan should add an explicit step to extend `FakeKnowledgeStore` with per-`repo` control — e.g. `results: dict[str | None, list[Chunk]]` and `errors: dict[str | None, Exception]` keyed by the `repo` argument (falling back to the current single `result`/`error` so the 7.1.1 contract tests stay green). Without this the verification points cannot be asserted as written.

**2. (Medium) `GatheredContext.neighbor_chunks` default must use `field(default_factory=list)`, not a literal `[]`.**
`GatheredContext` is a `@dataclass(frozen=True)` (`src/reasoning/reasoner.py:14`). Task 1 says "Default it to an empty list"; taken literally as `neighbor_chunks: list[Chunk] = []` this raises `ValueError: mutable default ... is not allowed` at class-definition time. The plan should pin the concrete form: `neighbor_chunks: list[Chunk] = field(default_factory=list)` (and add `field` to the `from dataclasses import` line). Minor but a guaranteed error if implemented verbatim.

**3. (Low) `FakeProjectGraph` must stub all five `ProjectGraph` abstract methods to be instantiable.**
`ProjectGraph` (`src/graph/store.py`) declares five abstractmethods: `add_edge`, `edges_from`, `neighbors`, `remove_seed_edges`, `replace_seed_edges`. Task 4 mentions only `neighbors`; a subclass that overrides just `neighbors` cannot be instantiated. The plan should note that the fake stubs the other four (as `FakeKnowledgeStore`/`FakeEpisodicStore` already stub their non-exercised abstract methods) — the pattern exists in the same file, so this is a reminder, not a redesign.

### Positive Notes
- The failure-isolation design is exactly right and directly answers the spec's sharpest guard (line 30): three separately-scoped try/excepts — org-wide discovery, `graph.neighbors`, and a *per-neighbor* handler inside the loop — so a single failing neighbor is dropped without swallowing the primary gather or the rest of the loop.
- Correctly excludes both the queried `repo` **and** `None` from the distinct-`Chunk.repo` retrieval-neighbor set — `Chunk.repo` is `str | None`, so the `None` exclusion is a real, easily-missed guard the plan calls out.
- Bare-identity discipline is threaded end to end (answer's `repo`, `neighbors` `to_repo`, `Chunk.repo`, every `query(repo=…)`), matching the spec's identity guard, and Task 4 point (2) asserts the store never receives an `org/repo` form.
- Folding lives in the shared `_gather_context` helper with an explicit "do not add a parallel step in `answer`" instruction, preserving the 8.1 `narrate` inheritance the spec and roadmap require.
- One-embedding invariant is preserved and explicitly tested (point 3): the embedding computed at the top of the helper is reused for discovery and every per-neighbor query, never re-embedded.
- Reuses `self._k` with no new retrieval-size constant, as the spec mandates; `repo=None` short-circuit keeps the 7.1 org-wide path byte-for-byte unchanged.
- Construction-site analysis is accurate: `Reasoner` is built only in `scripts/eval.py` and the conftest fixture, and Task 4 updates the fixture in lockstep with Task 2's new required `graph` parameter — so a non-default injected dependency is safe and consistent with the other injected deps.

The plan is architecturally sound and spec-faithful; the findings above are fixable within the plan's own file boundary (Tasks 1 and 4) and should be closed before implementation.
