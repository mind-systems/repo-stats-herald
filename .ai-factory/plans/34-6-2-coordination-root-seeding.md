# Plan: 6.2 — Coordination-root seeding

## Context
Turn a coordination-root repository's authoritative `CLAUDE.md` (a repo that declares
itself a coordination layer and lists its member sub-projects and their contracts) into
precise `source=seed` project-graph edges, re-derived atomically from the **canonical ref**
on every canonical push and on backfill — never from a feature branch.

## Settings
- Testing: yes (recognizer, parser, and the atomic seed-replace are silent-failure surfaces — wrong/empty/mixed edges, no crash)
- Logging: minimal
- Docs: no

## Key design decisions (read before implementing)

- **All seeded edges are anchored at the coordination repo as `from_repo`.**
  `seed(repo, org_id)` produces edges `repo -> member` typed by the declared relationship.
  This is the only model consistent with the *fixed* 6.1.1 contract: `remove_seed_edges(from_repo)`
  filters by `from_repo`, and the spec calls `remove_seed_edges(repo)` with the coordination
  repo — so the removed set can equal the previously-inserted set only if every seed edge's
  `from_repo` is that coordination repo. `neighbors(coordination_repo)` then returns its members.
  (Assumption, forced by the fixed contract; if member→member edge direction is ever required
  it would need a contract change to `remove_seed_edges` and is out of scope here.)

- **Edge-kind mapping** follows the [coordination-root format](../../docs/behavior/coordination-root-format.md): the Relationship cell's keyword — contract → `CONTRACT`, auth → `AUTH`, else `DEPENDENCY`.

- **Atomicity needs a new store primitive.** The existing `remove_seed_edges` and `add_edge`
  each acquire their own connection and auto-commit, so calling them in sequence is *not* one
  transaction and cannot satisfy the "survives concurrent same-repo seeds" guard. Add a single
  transactional `replace_seed_edges(from_repo, edges)` to `ProjectGraph` instead (deviation from
  the spec's Files list, which named only `coordination.py`/`sync.py` — necessary because the seam
  cannot compose two auto-committing methods into one transaction). It reuses 6.1.2's config-wins
  conflict strategy (`ON CONFLICT DO NOTHING`), so config edges are untouched — not re-implemented.

- **No fetch.** `seed` opens `mirror.tree(repo, org_id, canonical_ref)` only; it never calls
  `mirror.ensure` (which fetches). It relies on the prior `ensure` already run by the enclosing
  `KnowledgeSync.backfill` / `on_push` flow before `seed` is invoked.

## Tasks

### Phase 1: Transactional seed-replace primitive

- [ ] **Task 1: Add `replace_seed_edges` to the project-graph store**
  Files: `src/graph/store.py`
  Add `replace_seed_edges(from_repo: str, edges: list[Edge]) -> None` to the `ProjectGraph` ABC
  (docstring: atomically replace all `source='seed'` rows for `from_repo` with `edges`; config
  rows untouched; serialized against concurrent same-repo calls). Implement in `PgProjectGraph`
  on a single acquired connection inside `async with conn.transaction():`
  1. Take a per-repo lock first: `SELECT pg_advisory_xact_lock(hashtextextended($1, 0))` on
     `from_repo` — forces two concurrent seeds of the same repo to serialize (a plain
     transaction alone can leave a mixed set when neither transaction's DELETE saw the other's
     snapshot-invisible inserts).
  2. `DELETE FROM project_edges WHERE from_repo = $1 AND source = 'seed'`.
  3. Insert each edge with the existing seed conflict clause
     (`INSERT ... ON CONFLICT (from_repo, to_repo, kind) DO NOTHING`) so a seed edge colliding
     with a `config` edge on the same triple leaves `config` in place.
  Keep `add_edge`/`remove_seed_edges`/`edges_from`/`neighbors` unchanged. No schema change.

### Phase 2: CoordinationSeeder

- [ ] **Task 2: `CoordinationSeeder` — recognition, parse, and seed** (depends on Task 1)
  Files: `src/graph/coordination.py` (new)
  Add `CoordinationSeeder` (constructor DI, per ARCHITECTURE.md — receives abstractions, wires
  nothing itself):
  - `__init__(self, mirror: RepoMirror, graph: ProjectGraph, canonical_refs: dict[str, str])`.
  - `_canonical_ref(repo)` — mirror of `KnowledgeSync._canonical_ref`: `canonical_refs.get(repo)`
    else `mirror.default_branch(repo)`. (Small deliberate duplication; `seed`'s signature is
    fixed to `(repo, org_id)` by the spec, so it must re-derive the ref rather than receive it.)
  - `is_coordination_root(claude_md: str) -> bool` — recognizes a coordination root by the marker
    the [coordination-root format](../../docs/behavior/coordination-root-format.md) defines (the
    `## Coordination` section). Returns `False` for an ordinary `CLAUDE.md` with no such section
    (false-positive guard) and `True` for a genuine one (false-negative guard). Keep the
    recognition/parse patterns private to this class ("owned details stay inside the owning class").
  - `_parse(claude_md: str, repo: str) -> list[Edge]` — parse **only** the `## Coordination` member
    table of the [coordination-root format](../../docs/behavior/coordination-root-format.md); every
    other table in the file (Commands, docs index, …) is ignored. Each member row becomes
    `repo -> member` tagged `source="seed"`, with the member's **bare `push.repo` identity** on both
    endpoints (never `org/repo`) and the kind from the format's Relationship column (contract →
    `CONTRACT`, auth → `AUTH`, else `DEPENDENCY`). The format doc — not the fixtures — is the ground
    truth for this shape; the Task 5 fixtures assert conformance to it.
  - `async def seed(self, repo: str, org_id: int) -> None`:
    resolve `canonical = self._canonical_ref(repo)`; open `with self._mirror.tree(repo, org_id,
    canonical) as tree:` and read `tree / "CLAUDE.md"`. Compute `edges`: `self._parse(text, repo)`
    when the file exists and `is_coordination_root(text)`; otherwise `[]` (missing file or not a
    coordination root). **Always** `await self._graph.replace_seed_edges(repo, edges)` — the empty
    case removes stale seed edges from a repo that stopped being a coordination root, rather than
    leaking them. Do **not** call `mirror.ensure` (no fetch). Log at info: repo, ref, edge count.

### Phase 3: Wire into 3.6 (KnowledgeSync) and the composition roots

- [ ] **Task 3: Call `seed` from `KnowledgeSync.backfill` and `on_push`** (depends on Task 2)
  Files: `src/knowledge/sync.py`
  Add an optional `seeder: CoordinationSeeder | None = None` constructor param (optional so the
  existing offline/test construction paths keep working and it mirrors the router's optional
  treatment of `knowledge_sync`). Store as `self._seeder`.
  - In `backfill`, after the indexing loop completes: `if self._seeder is not None: await
    self._seeder.seed(repo, org_id)`.
  - In `on_push`, after the indexing loop — and crucially **after** the existing
    `if push.branch != canonical: return` gate — call `await self._seeder.seed(push.repo,
    push.org_id)` when a seeder is present. Placing it past the gate is what guarantees a
    `CLAUDE.md` change on a feature branch never re-seeds the graph.
  Import `CoordinationSeeder` for typing only (feature depends on the graph feature's public
  class, per the dependency rules).

- [ ] **Task 4: Wire the seeder at both composition roots** (depends on Task 3)
  Files: `src/main.py`, `scripts/backfill.py`
  - `src/main.py`: inside the existing GitHub-App/mirror-gated block (where `mirror` and the
    `PgProjectGraph graph` already exist), build
    `seeder = CoordinationSeeder(mirror, graph, settings.canonical_refs)` and pass it into
    `KnowledgeSync(mirror, indexer, strategy, settings.canonical_refs, seeder=seeder)`. `graph` is
    already constructed and schema already applied earlier in `lifespan`.
  - `scripts/backfill.py`: apply the graph schema alongside the knowledge schema (add
    `GRAPH_SCHEMA_PATH` and execute it), construct `PgProjectGraph(pool)` and
    `CoordinationSeeder(mirror, graph, settings.canonical_refs)`, and pass `seeder=` into the
    `KnowledgeSync(...)` construction so the offline backfill also seeds.

### Phase 4: Tests

- [ ] **Task 5: Seeder unit tests** (depends on Task 2)
  Files: `tests/graph/test_coordination_seeder.py` (new), fixtures as inline strings or under `tests/graph/fixtures/`
  Cover the spec's verification cases against `is_coordination_root` / `_parse` (pure string
  inputs) and `seed` (with a fake mirror whose `tree(...)` context manager yields a tmp dir
  containing a `CLAUDE.md`, and a fake or real `ProjectGraph`):
  - a coordination `CLAUDE.md` listing members `api`, `mobile` (bare names) with a contract note →
    the expected `CONTRACT`/`DEPENDENCY` seed edges, both endpoints bare (`from_repo` = the
    coordination repo);
  - an all-three-kinds fixture → contract→`CONTRACT`, auth→`AUTH`, membership→`DEPENDENCY` each verified;
  - a coordination `CLAUDE.md` that ALSO carries an unrelated table (e.g. a Commands table with
    `make run`/`make eval` rows) → edges seeded **only** for the `## Coordination` members, none for
    the other table's rows (the member-table-scope guard);
  - an ordinary (non-coordination) `CLAUDE.md` → `is_coordination_root` false and `seed` produces
    no edges (false-positive guard); a genuine one → recognized (false-negative guard);
  - editing the fixture to drop a member and re-seeding removes only the dropped member's edge and
    leaves a planted `config` edge intact;
  - a repo that drops the `## Coordination` section (or whose `CLAUDE.md` is deleted) → re-seeding
    removes all its seed edges while the planted `config` edge survives (the de-classification guard).

- [ ] **Task 6: `replace_seed_edges` store tests** (depends on Task 1)
  Files: `tests/graph/test_project_graph_contract.py` (extend) — reuses the `store`/`make_edge`/`pg_pool` fixtures in `tests/graph/conftest.py`
  Add tests on the real pgvector pool:
  - atomic replace: seed set `{a→b, a→c}`, then `replace_seed_edges("a", {a→b})` leaves exactly
    `{a→b}` seed-sourced and preserves any `config` edge on `a`;
  - concurrent convergence: two `replace_seed_edges("a", ...)` calls with *different* edge sets run
    via `asyncio.gather` end in exactly one complete set (never a mix of both) — the advisory-lock /
    transaction serialization guard.
