# Plan: 6.1.1 — Project graph contract + schema (red tests)

## Context
Introduce the project-graph seam — the registry of directed, typed cross-project edges Herald cannot infer from retrieval — as an edge model, a storage-agnostic `ProjectGraph` ABC, the `project_edges` schema, and a raising stub, then pin the config-wins-on-collision invariant (and the graph's other correctness properties) with red tests ahead of the Postgres implementation in 6.1.2.

## Settings
- Testing: yes (the red tests are the task's core deliverable)
- Logging: minimal
- Docs: no

## Notes for the implementer
- **New feature package** `src/graph/`, following the existing `src/knowledge/` and `src/episodic/` shape: a `models.py` value object, a `store.py` with the ABC + a concrete class, and a co-located `schema.sql` (this project ships each module's DDL as an idempotent `schema.sql` applied by the test's `pg_pool` fixture — there is no separate migrations directory; follow that convention rather than inventing one).
- **Red-test discipline (spec Guards):** the stub's methods raise, so every test fails *only* because there is no add/query/remove logic yet. 6.1.2 (`PgProjectGraph` impl, spec `.ai-factory/specs/09-project-graph-registry.md`) turns these tests green by filling in method bodies — never by editing the tests. To keep the test target stable across 6.1.1 → 6.1.2, the concrete class the tests instantiate is named `PgProjectGraph` from the start: in this task its methods `raise NotImplementedError`; in 6.1.2 the bodies are implemented.
- **The collision hazard is a store-level property**, so its test must run against a real `project_edges` table (via the `pg_pool` fixture) exactly like `tests/episodic/test_episodic_store_contract.py` — asserting the DB-enforced behavior the stub does not yet provide.
- Config/architecture: this is a feature package depending only on infra; the ABC names no storage concept (spec Guards). `Edge` is immutable, mirroring `Chunk`/`EpisodicEntry` (`@dataclass(frozen=True)`).

## Tasks

### Phase 1: Edge model, schema, and the ABC + stub

- [x] **Task 1: Edge value object and EdgeKind enum**
  Files: `src/graph/__init__.py` (new, empty), `src/graph/models.py` (new)
  Define `EdgeKind` as a `enum.StrEnum` (Python 3.12) with members `CONTRACT = "CONTRACT"`, `AUTH = "AUTH"`, `DEPENDENCY = "DEPENDENCY"` — a str-valued enum so its members map directly to the `kind` text column. Define `Edge` as an immutable value object (`@dataclass(frozen=True)`, matching `src/knowledge/store.py::Chunk` and `src/episodic/models.py::EpisodicEntry`) with fields: `from_repo: str`, `to_repo: str`, `kind: EdgeKind`, `source: str` (values `"config"` | `"seed"`; kept a plain `str` per the spec's Files & types, not an enum). No behavior — a pure DTO.

- [x] **Task 2: `project_edges` schema**
  Files: `src/graph/schema.sql` (new)
  Idempotent DDL (`CREATE TABLE IF NOT EXISTS project_edges`) with columns `from_repo text NOT NULL`, `to_repo text NOT NULL`, `kind text NOT NULL`, `source text NOT NULL`, and `PRIMARY KEY (from_repo, to_repo, kind)` — deliberately excluding `source` from the key, because that exclusion is the exact collision hazard the red tests pin (spec Change / Guards); do not "fix" it by widening the PK. Keep it plain SQL with no pgvector dependency (this table has no embeddings), so it applies cleanly alongside Phase 3's tables on the same pool (spec Verification). A CHECK constraint on `source IN ('config','seed')` / `kind IN (...)` is optional and out of scope — omit unless trivially added; the invariant under test is source-preservation on collision, not column validation.

- [x] **Task 3: `ProjectGraph` ABC + raising stub** (depends on Task 1)
  Files: `src/graph/store.py` (new)
  Define `ProjectGraph(ABC)` naming no storage concept (spec Guards), mirroring the ABC style of `src/knowledge/store.py::KnowledgeStore` — each method `@abstractmethod` with a docstring stating the contract:
  - `async def add_edge(self, edge: Edge) -> None` — persist `edge`; a `source='seed'` write that collides with an existing edge on the same `(from_repo, to_repo, kind)` triple must NOT downgrade a stored `config` edge's `source`, and re-adding an identical `config` edge is idempotent (no duplicate, no error).
  - `async def edges_from(self, repo: str) -> list[Edge]` — every stored edge whose `from_repo == repo`, hydrated with its stored `source`.
  - `async def neighbors(self, repo: str) -> list[str]` — the `to_repo` of every edge `repo→…`; directed, never symmetric.
  - `async def remove_seed_edges(self, from_repo: str) -> None` — delete only rows with `source='seed'` for that `from_repo`; `config` rows untouched.
  Then a concrete `PgProjectGraph(ProjectGraph)` taking `pool: asyncpg.Pool` in its constructor (matching `PgEpisodicStore`), whose four methods currently `raise NotImplementedError`. This is the stub 6.1.2 fills in; naming it `PgProjectGraph` now keeps the test target stable through that transition.

### Phase 2: Red tests against the stub + schema

- [x] **Task 4: Test fixtures for the graph store** (depends on Task 2, Task 3)
  Files: `tests/graph/__init__.py` (new, empty), `tests/graph/conftest.py` (new)
  Model on `tests/episodic/conftest.py`: reuse the same `_dsn()` env-driven DSN builder and `create_pool` from `src.core.db`. Provide a `pg_pool` fixture that reads `src/graph/schema.sql` (via `Path(__file__).resolve().parents[2] / "src" / "graph" / "schema.sql"`), executes it, and `TRUNCATE project_edges` before yielding; a `store` fixture returning `PgProjectGraph(pg_pool)`; and a `make_edge` factory fixture (`Callable[..., Edge]`) with sensible defaults (`from_repo="org/a"`, `to_repo="org/b"`, `kind=EdgeKind.CONTRACT`, `source="config"`) so each test states only the fields it cares about.

- [x] **Task 5: The four pinned red tests** (depends on Task 4)
  Files: `tests/graph/test_project_graph_contract.py` (new)
  One async test per spec Change/Verification case, each awaiting `store` methods (which raise now → red):
  - **config survives a colliding seed** — `add_edge` a `config` edge for `(a, b, CONTRACT)`, then `add_edge` a `seed` edge for the identical triple; assert the matching edge in `edges_from("a")` still reports `source == "config"` (never downgraded to `seed`).
  - **seed-only removal** — plant a `config` edge and a `seed` edge under the same `from_repo` (different `to_repo`/triple); call `remove_seed_edges(from_repo)`; assert `edges_from(from_repo)` retains the `config` edge and drops the `seed` edge.
  - **directed neighbors** — `add_edge` a single `a→b` edge; assert `neighbors("a") == ["b"]` and `neighbors("b") == []` (no symmetry); add a separate `b→a` edge and assert `a` then appears in `neighbors("b")`.
  - **idempotent config reload** — `add_edge` the same `config` edge twice; assert `edges_from` returns exactly one matching edge and neither call errored.
  Keep assertions on the observable contract (returned `Edge`s / neighbor lists), not on SQL internals, so 6.1.2's implementation greens them without test edits.
