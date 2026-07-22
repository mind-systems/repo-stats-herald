## Plan Review Summary

**Plan:** 6.1.1 — Project graph contract + schema (red tests)
**Files Reviewed:** plan + governing spec `47-project-graph-contract.md` + downstream spec `09-project-graph-registry.md` + codebase (`src/episodic/`, `src/knowledge/`, `src/core/db.py`, `tests/episodic/conftest.py`, `tests/episodic/test_episodic_store_contract.py`, ROADMAP, ARCHITECTURE, RULES)
**Risk Level:** 🟢 Low

### Context Gates
- **Architecture (`.ai-factory/ARCHITECTURE.md`) — OK.** `src/graph/` is a self-contained feature package owning its `models.py`/`store.py`/`schema.sql`, depending only on infra (`asyncpg`, and `src.core.db.create_pool` in the test fixture) and never on another feature. The `ProjectGraph` ABC names no storage concept and `PgProjectGraph` takes a `pool` by constructor injection — matching the DI-at-composition-root discipline and the `EpisodicStore`/`KnowledgeStore` seam pattern exactly.
- **Rules (`.ai-factory/RULES.md`) — OK.** File is intentionally empty (no project counter-defaults); nothing to enforce.
- **Roadmap (`.ai-factory/ROADMAP.md`) — OK.** The plan's `# Plan:` heading matches roadmap line 69 (task 6.1.1). Governing spec for 6.1.1 is `47-project-graph-contract.md`; the plan's references to `09-project-graph-registry.md` are correctly attributed to the *downstream* 6.1.2 task (roadmap line 70 confirms 09 is 6.1.2's spec). No mis-citation.
- **Skill-context (`aif-review/SKILL.md`) — absent.** No project-specific review overrides.

### Critical Issues
None.

### Correctness / Alignment Notes (verified, no action required)
- **Model placement is correct.** Spec 47 §Files & types puts `Edge`/`EdgeKind` in `src/graph/models.py`; the plan's Task 1 matches. The frozen-dataclass reference to `src/knowledge/store.py::Chunk` is accurate (`Chunk` is defined in `store.py`, `@dataclass(frozen=True)`), as is `src/episodic/models.py::EpisodicEntry`.
- **The `schema.sql`-vs-"migration" deviation is a correct one.** Spec 47 says "migration for `project_edges`"; the plan ships a co-located idempotent `src/graph/schema.sql` applied by the `pg_pool` fixture. This follows ground truth — `src/episodic/schema.sql` and the knowledge module use exactly this pattern, and there is no migrations directory in the repo. The plan explicitly justifies the divergence rather than silently inventing a directory. Conformance, not a defect.
- **PK excludes `source` — pinned deliberately.** Task 2's `PRIMARY KEY (from_repo, to_repo, kind)` reproduces the exact collision hazard spec 47 §9 and the roadmap line describe. The note "do not fix it by widening the PK" is right: config-wins is enforced by 6.1.2's conflict strategy, not the key.
- **Red-test discipline is sound.** With the stub raising `NotImplementedError`, all four tests fail for the single intended reason (no logic yet). Naming the concrete `PgProjectGraph` from the start keeps the 6.1.1→6.1.2 test target stable, matching `PgEpisodicStore(pool)` construction. 6.1.2's `ON CONFLICT DO NOTHING` (seed) / `DO UPDATE` (config) strategy greens each assertion without test edits — I traced all four cases (config-survives-collision, seed-only removal, directed neighbors, idempotent reload) against the 09 impl plan and they hold.
- **Fixture plan is accurate.** `tests/episodic/conftest.py` confirms every reused element the plan cites: the `_dsn()` builder, `create_pool` from `src.core.db`, the `SCHEMA_PATH = parents[2] / "src" / <module> / "schema.sql"` idiom, the `pg_pool` schema-apply-then-`TRUNCATE` shape, the `store` fixture, and the `make_*` factory pattern. `asyncio_mode = "auto"` in `pyproject.toml` means the bare `async def` tests run without decorators — consistent with the plan's "one async test per case."
- **The four test cases map 1:1 to spec 47 §Change/§Verification** — no invented contract, no missing case.

### Positive Notes
- Strong grounding: the plan reads the neighboring modules and mirrors their exact conventions (frozen DTO, ABC+concrete split, co-located `schema.sql`, fixture idioms) rather than improvising.
- The collision hazard is correctly identified as a *store-level* property requiring the real `project_edges` table via `pg_pool`, not a pure-Python unit test — matching spec 47's "explicit and adversarial" guard.
- Task dependencies (Task 3→1, Task 4→2,3, Task 5→4) are ordered correctly and the stub-raises/tests-red invariant is stated unambiguously so 6.1.2 cannot be tempted to edit tests instead of bodies.

## Deferred observations
- Affects: machine/environment setup (out of this task's file boundary) — `src.core.db.create_pool` registers a text codec for the pgvector `vector` type on every connection, so it requires the `vector` extension to already exist in `herald_database` even though `src/graph/schema.sql` deliberately (and correctly) carries no vector column or `CREATE EXTENSION`. This is satisfied today by the once-per-machine setup and by `src/episodic/schema.sql` creating the extension, so the graph tests pass as planned; it is only a latent coupling worth remembering if a graph-only test DB is ever provisioned in isolation. Nothing to change in this plan.

PLAN_REVIEW_PASS
