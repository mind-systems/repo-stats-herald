# Plan: 6.2 — Coordination-root seeding

## Context
Materialize a coordination-root repo's `## Coordination` member table (published [coordination-root format](../../docs/behavior/coordination-root-format.md)) into precise `source=seed` project-graph edges, re-seeded atomically on every canonical-ref push/backfill so the graph tracks the repo's current authoritative structure without operator entry.

## Settings
- Testing: yes (parsing/recognition/kind-mapping and atomic-replace are silent-failure surfaces — wrong edges, no crash — and the spec's Verification section enumerates the cases)
- Logging: minimal
- Docs: no (the behavior contract already lives in `docs/behavior/coordination-root-format.md`)

## Ground-truth notes (verified against code)
- `ProjectGraph` (`src/graph/store.py`) today exposes `add_edge` (seed insert uses `ON CONFLICT DO NOTHING`, so a `config` edge on the same `(from,to,kind)` triple always survives) and `remove_seed_edges` — but these are **two separate transactions**, so they cannot satisfy 6.2's "remove-then-insert is transactional / concurrent seeds serialize" guard. An atomic replace method must be added to the graph. This extends the spec's explicit file list (`coordination.py` + `sync.py`) with `src/graph/store.py`, required by the spec's atomicity guard.
- `Edge` is `frozen` with `from_repo/to_repo/kind: EdgeKind/source: str` (`src/graph/models.py`); `EdgeKind` = `CONTRACT|AUTH|DEPENDENCY`.
- `PushEvent.repo` is the **bare** GitHub repo name (`payload["repository"]["name"]`); `seed`'s `repo` arg is already bare — use it verbatim on both endpoints (`from_repo=repo`, `to_repo=member`), never `org/repo`.
- `RepoMirror.tree(repo, org_id, ref)` is a context manager yielding a checked-out worktree `Path`; `default_branch(repo)` reads the bare mirror's HEAD and requires the bare clone to already exist. The seeder must **not** call `ensure`/fetch (guard: no network fetch) — `KnowledgeSync.backfill`/`on_push` already call `mirror.ensure(...)` before reaching the seed call.
- `KnowledgeSync` (`src/knowledge/sync.py`) already resolves the canonical ref via `_canonical_ref` and gates `on_push` on `push.branch == canonical` (returning early for feature branches) — seeding rides inside this gate, so a feature-branch `CLAUDE.md` change never re-seeds.
- Graph tests (`tests/graph/`) run against a live Postgres using the concrete `PgProjectGraph` — there is no in-repo fake implementing the `ProjectGraph` ABC, so adding an abstract method only requires implementing it in `PgProjectGraph`.
- `KnowledgeSync.backfill` has exactly **one** caller — `scripts/backfill.py:57` — which is a second composition root (ARCHITECTURE names both `src/main.py` and `scripts/*.py` as composition roots). It today creates only the knowledge pool and applies **only** `src/knowledge/schema.sql`; it constructs no `PgProjectGraph`. So the seeder must be wired there too, or backfill seeding is a dead path.
- Stale `src/graph/__pycache__/coordination.*.pyc` and `tests/graph/__pycache__/test_coordination_seeder.*.pyc` exist with no `.py` sources (a prior rolled-back attempt); they are harmless and can be ignored.

## Tasks

### Phase 1: Atomic seed-edge replacement in the graph

- [x] **Task 1: Add transactional `replace_seed_edges` to the project graph**
  Files: `src/graph/store.py`
  Add `async def replace_seed_edges(self, from_repo: str, edges: list[Edge]) -> None` to the `ProjectGraph` ABC (docstring: atomically replace the repo's entire `source='seed'` set — delete prior seed rows and insert `edges` in one transaction; `config` rows untouched; concurrent replaces for the same `from_repo` serialize). Implement in `PgProjectGraph` on a single acquired connection inside `async with conn.transaction():`
  - Take a per-repo serialization lock first: `await conn.execute("SELECT pg_advisory_xact_lock(hashtext($1))", from_repo)` so two concurrent replaces of the same repo cannot interleave into a partial/duplicated set (they queue; last transaction's set wins).
  - `DELETE FROM project_edges WHERE from_repo = $1 AND source = 'seed'` (never touches `source='config'`).
  - Insert every edge in `edges` with `INSERT ... ON CONFLICT (from_repo, to_repo, kind) DO NOTHING` (mirrors `add_edge`'s seed path — a seed edge colliding with an existing `config` edge does nothing, so operator edges always win the triple). Use `executemany` or a loop over the same `conn`.
  Follow the existing SQL/param style in `add_edge`.

### Phase 2: The coordination seeder

- [x] **Task 2: Implement `CoordinationSeeder`** (depends on Task 1)
  DEVIATION: plan said `_parse_members(self, claude_md: str) -> list[Edge]` / `Edge` is a frozen dataclass with a required `from_repo` field so a complete `Edge` cannot be built without it / implemented as `_parse_members(self, claude_md: str, from_repo: str) -> list[Edge]`, called from `seed` as `self._parse_members(text, repo)`.
  Files: `src/graph/coordination.py` (new)
  Class `CoordinationSeeder` assembled by constructor DI (feature-modular OOP + DI): `__init__(self, mirror: RepoMirror, graph: ProjectGraph, canonical_refs: dict[str, str])`. No concrete construction inside; no env reads. Methods:
  - `is_coordination_root(self, claude_md: str) -> bool` — `True` iff the text contains a `## Coordination` section heading (a line whose stripped form is `## Coordination`). An ordinary `CLAUDE.md` without it is not a coordination root.
  - `_parse_members(self, claude_md: str) -> list[Edge]` (internal) — isolate the `## Coordination` section (from its heading to the next `## ` heading or EOF), parse its single Markdown pipe table, and map each **member row** to one `Edge`:
    - For each table row split on `|` and strip cells, then **trim only the leading/trailing empty boundary cells** produced by the row's outer `|` delimiters (e.g. `| api | contract: x |` → `['', 'api', 'contract: x', '']` → boundary-trim → `['api', 'contract: x']`). Trim boundaries only — do **not** blanket-drop every empty cell, or an empty-Member row would collapse and mis-map instead of being skipped. After trimming, cell[0] is Member, cell[1] is Relationship (missing → empty string).
    - Skip the header row (Member cell, lowercased, `== "member"`), the separator row (cells made only of `-`/`:`/spaces), and any row whose Member cell is empty.
    - `to_repo` = the bare Member cell (cell[0]); `from_repo` is supplied by `seed` (the bare coordination-root repo name).
    - Kind from the **first token** of the Relationship cell (split on whitespace and `:`, lowercased): `contract` → `EdgeKind.CONTRACT`, `auth` → `EdgeKind.AUTH`, anything else or empty → `EdgeKind.DEPENDENCY`. Per the format doc, text after the first token is descriptive detail and ignored.
    - Every edge is built with `source="seed"`.
  - `async def seed(self, repo: str, org_id: int) -> None`:
    - Resolve the canonical ref the same way `KnowledgeSync` does: `self._canonical_refs.get(repo)`, falling back to `self._mirror.default_branch(repo)` (factor a private `_canonical_ref(repo)` helper mirroring `KnowledgeSync._canonical_ref`; note the small intentional duplication — `seed(repo, org_id)`'s signature is fixed by the spec, so it cannot receive a pre-resolved ref).
    - Read `CLAUDE.md` from an isolated tree at that ref: `with self._mirror.tree(repo, org_id, canonical) as tree:` then read `tree / "CLAUDE.md"`. If the file is missing OR `is_coordination_root` is `False`, the parsed edge list is **empty** (a repo that stopped being a coordination root drops its stale seeds). Otherwise `edges = self._parse_members(text)` with `from_repo=repo` on each (bare identity both ends).
    - Atomically apply: `await self._graph.replace_seed_edges(repo, edges)` (Task 1) — one transaction, so a re-seed never leaves a partial set and config edges are untouched.
    - Do **not** call `mirror.ensure`/fetch — the caller has already ensured the mirror; guard: no network fetch here.
    - Minimal `logger.info` line: repo, canonical ref, whether recognized as a coordination root, edge count.

### Phase 3: Wiring into the canonical-ref sync path

- [x] **Task 3: Call `seed` from `KnowledgeSync.backfill` and the canonical branch of `on_push`** (depends on Task 2)
  Files: `src/knowledge/sync.py`
  Add an optional `seeder: CoordinationSeeder | None = None` constructor parameter (store as `self._seeder`), keeping existing `KnowledgeSync(...)` callers/tests that omit it working. Invoke seeding **after** semantic memory is populated for the canonical ref:
  - End of `backfill(repo, org_id)`, after the indexing loop/log: `if self._seeder is not None: await self._seeder.seed(repo, org_id)`.
  - In `on_push(push)`, after the canonical-ref indexing block (i.e. only on the path that did not `return` early for a non-canonical branch): `if self._seeder is not None: await self._seeder.seed(push.repo, push.org_id)`. This keeps seeding gated to the canonical ref — a feature-branch push returns before reaching it.
  Import `CoordinationSeeder` from `src.graph.coordination` for the type hint.

- [x] **Task 4: Wire the seeder at both composition roots** (depends on Task 2, Task 3)
  Both `KnowledgeSync` composition roots must build and inject the seeder, otherwise the spec-required backfill seeding is a dead path (`backfill`'s only caller is `scripts/backfill.py`).
  - `src/main.py`: inside the existing `if settings.github_app_id ... :` block (where `mirror` and the `graph = PgProjectGraph(pool)` built earlier at lifespan start are both in scope), construct `seeder = CoordinationSeeder(mirror, graph, settings.canonical_refs)` and pass it into the existing `KnowledgeSync(...)` construction as the new `seeder` argument. Add the `from src.graph.coordination import CoordinationSeeder` import. No new state attribute is needed — the seeder lives inside `KnowledgeSync`.
  - `scripts/backfill.py`: this root today creates only the knowledge pool and applies **only** `src/knowledge/schema.sql`, and constructs no graph. To make backfill seeding runnable, additionally: (a) apply the graph schema — add a `GRAPH_SCHEMA_PATH` (`.../src/graph/schema.sql`) and `await conn.execute(GRAPH_SCHEMA_PATH.read_text())` alongside the existing knowledge-schema apply; (b) construct `graph = PgProjectGraph(pool)`; (c) construct `seeder = CoordinationSeeder(mirror, graph, settings.canonical_refs)` and pass it into the `KnowledgeSync(...)` construction (line 57). Add imports `from src.graph.store import PgProjectGraph` and `from src.graph.coordination import CoordinationSeeder`.

### Phase 4: Tests

- [x] **Task 5: Tests for the seeder and atomic replace** (depends on Task 1, Task 2)
  Files: `tests/graph/test_coordination_seeder.py` (new), and extend `tests/graph/test_project_graph_contract.py`
  Follow the existing `tests/graph/conftest.py` fixtures (live Postgres `pg_pool`/`store`, `TRUNCATE project_edges`). For the seeder, use a fake/stub `RepoMirror` (or a small stub graph) so no real git/network is needed — a stub whose `tree` context manager yields a `tmp_path` containing a crafted `CLAUDE.md`, and whose `default_branch` returns a fixed ref. Cover the spec's Verification cases:
  - `is_coordination_root`: a `CLAUDE.md` with `## Coordination` → `True`; an ordinary one → `False` (false-positive / false-negative checks).
  - Parsing: a table with `contract`, `auth`, and plain-membership rows → `CONTRACT`/`AUTH`/`DEPENDENCY` edges respectively, `source='seed'`, both endpoints bare (`from_repo` = the coordination-root name, `to_repo` = bare member).
  - Other tables ignored: a `CLAUDE.md` with a Commands table plus `## Coordination` seeds edges only for the members.
  - Replace semantics (against the real `PgProjectGraph`): editing the table to drop a member removes that edge; dropping the `## Coordination` section (or missing file) removes all of that repo's seed edges; a pre-planted `source='config'` edge on the same triple survives a seed cycle (source stays `config`).
  - `replace_seed_edges` (contract test): pre-plant one `config` and one `seed` edge for a repo, `replace_seed_edges(repo, [<new seed set>])` → old seed rows gone, new seed rows present, the `config` row untouched.
  - Concurrent-seed serialization (the reason Task 1's `pg_advisory_xact_lock` exists): run two `replace_seed_edges(repo, ...)` calls for the **same** repo concurrently (e.g. `asyncio.gather` over the real `PgProjectGraph` on distinct edge sets A and B) and assert the graph's end state is exactly one of the two full sets — never a partial mix or duplicated union. This verifies the spec's final Verification bullet (consistent end state under concurrency).
