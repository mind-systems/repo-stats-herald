# 6.1.1 — Project graph contract + schema (red tests)

**Phase:** 6 — Project graph & the cross-project surface. First task. The registry of cross-project links Herald cannot infer from retrieval, pinned with red tests ahead of the Postgres implementation (6.1.2).

## Current state

Declared relationships (a per-repo `CLAUDE.md` naming the proto it owns) already live in the knowledge store and surface through retrieval (see `docs/spec/understanding.md#project-graph`). The links that are **not** written down — two tightly-coupled repos that cross-reference nothing — have no home. There is no edge model, no store, no way to declare them.

Worse, the natural schema has a sharp silent trap: the `project_edges` primary key is `(from_repo, to_repo, kind)` — it **excludes** `source`. Two different writers touch this table: an operator's config (loaded once at startup, tagged `source=config`) and 6.2's coordination-root seeder (re-run on every canonical-ref push touching a `CLAUDE.md`, tagged `source=seed`). If a seed write ever produces the same `(from_repo, to_repo, kind)` triple as an existing config edge, the PK collision means the seed write either **silently overwrites the row's `source` from `config` to `seed`** — making an operator-declared edge deletable by the next `remove_seed_edges` call — or fails with no signal, depending on the conflict strategy. The guard "config never overwritten by seeding" is asserted in prose today with nothing proving it survives this exact collision.

## Change

Define the edge model, the `ProjectGraph` ABC, and the schema, then pin the config-wins-on-collision invariant (and the graph's other correctness properties) with red tests before writing the Postgres implementation.

- `src/graph/models.py` — `Edge` (immutable): `from_repo: str`, `to_repo: str`, `kind: EdgeKind` (`CONTRACT` / `AUTH` / `DEPENDENCY`), `source: str` (`config` | `seed`).
- `project_edges` table (migration, on Herald's Postgres from Phase 3): `from_repo`, `to_repo`, `kind`, `source`, `PRIMARY KEY (from_repo, to_repo, kind)`.
- `src/graph/store.py` — `ProjectGraph` (ABC): `add_edge(edge)`, `edges_from(repo) -> list[Edge]`, `neighbors(repo) -> list[str]`, `remove_seed_edges(from_repo)`. Names no storage concept. A STUB implementation raises for now.
- Write red tests against the stub/schema pinning:
  - **config survives a colliding seed** — plant a `config` edge for `(a, b, CONTRACT)`, then run a seed cycle (`add_edge` tagged `source=seed`) for the same triple; `edges_from("a")`'s matching edge still reports `source="config"`, never downgraded;
  - `remove_seed_edges(repo)` deletes only rows where `source='seed'` for that repo — a `config` edge for the same `from_repo` is untouched;
  - `neighbors(repo)` is **directed** — an edge `a→b` makes `b` a neighbor of `a`, but not the reverse, unless a separate `b→a` edge exists;
  - re-loading the same configured edge is idempotent (no duplicate row, no error).

## Files & types

- new `src/graph/__init__.py`, `src/graph/models.py` (`Edge`, `EdgeKind`), `src/graph/store.py` (`ProjectGraph` ABC + stub), migration for `project_edges`
- new test file(s) covering the four cases above, run against the stub/schema (red)

## Guards

- Tests-first: the stub raises rather than persisting — 6.1.2 turns these tests green, never the reverse.
- The config-survives-collision test is explicit and adversarial (a planted config edge, then a colliding seed write) — a test that only checks each writer in isolation would not catch this interaction.
- `ProjectGraph` is a seam — names no storage concept; the backing (a Postgres table now) swaps without touching callers.
- Edges are **directed** and typed; `(from_repo, to_repo, kind)` is the schema's unique key — the collision hazard above is a direct consequence of this choice, not an accident to paper over.

## Verification

- The test suite added here is red against the stub (fails only because there's no add_edge/query/remove logic yet).
- The schema applies cleanly alongside Phase 3's tables (same Postgres pool).
- Each of the four pinned cases (config-survives-collision, seed-only removal, directed neighbors, idempotent config reload) has a corresponding red test.
