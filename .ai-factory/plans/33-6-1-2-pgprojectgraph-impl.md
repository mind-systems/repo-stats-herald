# Plan: 6.1.2 — PgProjectGraph (impl)

## Context
Implement `PgProjectGraph` over 6.1.1's `project_edges` schema and Phase 3's asyncpg pool, using a conflict strategy where `config` edges win any triple collision by construction, plus operator-declared edge config loaded once and injected into the graph at the composition-root startup — greening 6.1.1's red suite (`tests/graph/test_project_graph_contract.py`).

## Settings
- Testing: no
- Logging: minimal
- Docs: no

## Notes for the implementer

- **Do NOT add or edit tests.** 6.1.1 already wrote the red suite (`tests/graph/test_project_graph_contract.py` + `tests/graph/conftest.py`). This task turns it green; the four cases (config-survives-collision, seed-only removal, directed neighbors, idempotent config reload) are the acceptance bar. Run them, don't rewrite them.
- **Ground truth already read:** `src/graph/store.py` (stub `PgProjectGraph`), `src/graph/models.py` (`Edge`/`EdgeKind` — `EdgeKind` is a `StrEnum`, `Edge` a frozen dataclass with `source: str`), `src/graph/schema.sql` (`PRIMARY KEY (from_repo, to_repo, kind)`, `source` excluded from the PK — this is the deliberate collision hazard). Follow the existing Pg store pattern in `src/episodic/store.py` / `src/knowledge/store.py` (acquire from pool, parameterized SQL, hydrate rows back into value objects).

- **Architecture reconciliation (important — read before touching config).** Spec `09-project-graph-registry.md` says "extend `Settings` with `project_edges` … parse into `Edge`s tagged `source=config`." Taken literally that makes `src/core/config.py` (infra) import `src/graph/models.py` (a feature) — a reverse dependency ARCHITECTURE.md forbids ("Features depend on infra modules, never the reverse"). Reconcile by keeping the *intent* (config parsed once via `Settings`, never read inline) while respecting the dependency rule: `Settings.project_edges` parses the operator string into a **graph-agnostic** structured form (a tuple of `(from_repo, to_repo, kind)` string triples); the composition root (`src/main.py`, which already imports `src/graph/`) maps each triple to `Edge(..., source="config")` and loads it. This satisfies both the spec's guard ("config parsed once at startup via `Settings`, not read inline") and the architecture. 6.1.1's tests do not exercise config parsing, so this shape choice does not affect greening.

## Tasks

### Phase 1: Store implementation

- [x] **Task 1: Implement `PgProjectGraph.add_edge` with the config-wins conflict strategy**
  Files: `src/graph/store.py`
  Replace the `add_edge` stub. Branch on `edge.source`:
  - `edge.source == "seed"` → `INSERT INTO project_edges (from_repo, to_repo, kind, source) VALUES ($1,$2,$3,$4) ON CONFLICT (from_repo, to_repo, kind) DO NOTHING` — a seed write colliding with any existing row (config *or* seed) is silently a no-op, so it can never downgrade a stored `config` edge's `source`.
  - `edge.source == "config"` → same INSERT but `ON CONFLICT (from_repo, to_repo, kind) DO UPDATE SET source = EXCLUDED.source` — a re-declared config edge refreshes cleanly (idempotent: same triple → one row, no error) and reasserts `source='config'` even if a seed row somehow landed first (the invariant holds by conflict strategy, not load-order timing).
  Bind `kind` as `edge.kind.value` (or `str(edge.kind)`) so a `text` column receives a plain string. Acquire a connection from `self._pool` following the `PgEpisodicStore.append` pattern. Keep the SQL/HTTP-level detail inside this class — callers see only `add_edge(edge)`.

- [x] **Task 2: Implement `edges_from`, `neighbors`, `remove_seed_edges`** (depends on Task 1)
  Files: `src/graph/store.py`
  Replace the three remaining stubs:
  - `edges_from(repo)` → `SELECT from_repo, to_repo, kind, source FROM project_edges WHERE from_repo = $1`, hydrating each row into `Edge(from_repo=..., to_repo=..., kind=EdgeKind(row["kind"]), source=row["source"])`. Return `list[Edge]`.
  - `neighbors(repo)` → `SELECT to_repo FROM project_edges WHERE from_repo = $1 ORDER BY to_repo` returning `list[str]`. Directed only (never symmetric) — the `WHERE from_repo = $1` guarantees this; `ORDER BY to_repo` gives deterministic output for the `== ["b"]` assertion.
  - `remove_seed_edges(from_repo)` → `DELETE FROM project_edges WHERE from_repo = $1 AND source = 'seed'` — deletes seed rows only, leaving `config` rows for the same `from_repo` untouched.

### Phase 2: Config parsing & startup wiring

- [x] **Task 3: Add `project_edges` to `Settings`** (parses to graph-agnostic triples)
  Files: `src/core/config.py`, `.env.example`
  Add a `project_edges` field parsed once from an operator env var `PROJECT_EDGES` in the form `from>to:kind,from2>to2:kind2` (comma-separated edges; each edge is `from_repo>to_repo:kind`). Follow the existing `Annotated[..., NoDecode]` + `@field_validator(..., mode="before")` idiom already used for `serve_allowlist`/`canonical_refs`:
  - Field type: `Annotated[tuple[tuple[str, str, str], ...], NoDecode]`, default `()`.
  - Validator: pass through an already-structured value (tuple/list) unchanged; otherwise split the string on `,`, skip empty tokens, split each on the first `>` then `:` into `(from_repo, to_repo, kind)`, strip whitespace, and return a tuple of triples. Do **not** import `Edge`/`EdgeKind` here — kind stays a raw string; enum validation happens at the composition root where `EdgeKind` is constructed.
  - **Normalize the `kind` token to upper-case** as the validator emits it (`kind.strip().upper()`). `EdgeKind`'s values are upper-case (`CONTRACT`/`AUTH`/`DEPENDENCY`), but spec 09's own operator example is lower-case (`a/x > a/y : contract`); upper-casing here makes both cases load without an operator-facing startup crash and pins one canonical form. Keep `from_repo`/`to_repo` case as-is (repo names are case-sensitive).
  - Raise a clear `ValueError` on a malformed token (missing `>` or `:`) so a bad env fails fast at startup rather than silently dropping an edge.
  - In `.env.example`, add a `PROJECT_EDGES` entry after the `GITHUB_ORG_LOGINS` block, mirroring the sibling entries' comment style — document the `from>to:kind,...` grammar, note kind is one of `CONTRACT`/`AUTH`/`DEPENDENCY` (case-insensitive, normalized to upper-case), give an example (e.g. `PROJECT_EDGES=mind_api>mind_mobile:CONTRACT`), and leave the value blank.

- [x] **Task 4: Load configured edges into the graph at startup** (depends on Task 1, Task 2, Task 3)
  Files: `src/main.py`
  In the `lifespan` composition root:
  - Add `GRAPH_SCHEMA_PATH = Path(__file__).resolve().parent / "graph" / "schema.sql"` alongside the existing schema-path constants, and apply it in the same startup `conn.execute(...)` block that applies the ingestion/knowledge/episodic schemas — so `project_edges` exists before any edge write.
  - Construct `graph = PgProjectGraph(pool)` and expose it on app state following the existing `app.state.<name> = ...` convention (e.g. `app.state.project_graph = graph`).
  - Before `yield` (i.e. before any push processing begins), iterate `settings.project_edges` and for each `(from_repo, to_repo, kind)` triple `await graph.add_edge(Edge(from_repo=from_repo, to_repo=to_repo, kind=EdgeKind(kind), source="config"))`. The `kind` token arrives already upper-cased from the Task-3 validator, so `EdgeKind(kind)` accepts it; it still raises `ValueError` on a genuinely unknown kind — acceptable fail-fast at startup. Import `Edge`, `EdgeKind` from `src.graph.models` and `PgProjectGraph` from `src.graph.store`.
  - Place the load unconditionally (it does not depend on the GitHub-App/mirror gate), so operator edges load even when canonical-ref sync is disabled. Log at info level how many config edges were loaded (structured, via the module `logger`, per the logging convention — never `print`).

## Verification

- `tests/graph/test_project_graph_contract.py` passes green (requires the dev pgvector Postgres from `.env.dev`; run via the project's pytest with `POSTGRES_*` reachable).
- Manual/described checks from spec 09: a configured `a/x>a/y:CONTRACT` loads at startup so `neighbors("a/x") == ["a/y"]` and `edges_from("a/x")` returns the typed `Edge` with `source="config"`; re-loading the same edge stays a single row; a seed write on that triple leaves `source` at `config`.
