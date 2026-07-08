# 6.1.2 — PgProjectGraph (impl)

**Phase:** 6 — Project graph & the cross-project surface. Depends on 6.1.1 (the `Edge`/`EdgeKind` model, the `ProjectGraph` ABC, the schema, and its red tests — including the config-survives-collision case). Second half of the graph milestone — turns 6.1.1's tests green.

## Current state

6.1.1 defines the edge model, the `ProjectGraph` ABC, and the `project_edges` schema, and pins its contract — most importantly, that a `config` edge survives a colliding seed write — with red tests. The stub implementation raises for every call — no Postgres logic, no config loading exists yet.

## Change

Implement `PgProjectGraph` over 6.1.1's schema, using a conflict strategy that makes config edges win by construction, and load operator-declared edges at startup.

- `src/graph/store.py` — `PgProjectGraph(ProjectGraph)`: backs the ABC on the `project_edges` table (Phase 3's asyncpg pool).
  - `add_edge(edge)` — when `edge.source == "seed"`, insert with **`ON CONFLICT (from_repo, to_repo, kind) DO NOTHING`** — if a row already exists for that triple (whichever `source` it carries), the seed write is silently a no-op rather than overwriting it. A `config`-sourced `add_edge` (used only at startup load) uses `ON CONFLICT ... DO UPDATE` so a re-declared config edge refreshes cleanly — config edges only ever collide with other config edges at startup, never with seed writes, since seed never overwrites.
  - `remove_seed_edges(from_repo)` — `DELETE FROM project_edges WHERE from_repo = $1 AND source = 'seed'`.
  - `edges_from`/`neighbors` — plain reads off the table, `neighbors` directed (only `from_repo → to_repo`).
- Extend `src/core/config.py` `Settings` with `project_edges` — parse an operator-declared edge list (e.g. `PROJECT_EDGES` = `from>to:kind,...`) into `Edge`s tagged `source=config`.
- At the composition root, load the configured edges into the graph at startup, before any push processing begins.

## Files & types

- edit `src/graph/store.py` (stub → `PgProjectGraph` implementation)
- edit `src/core/config.py` (`Settings.project_edges`)

## Guards

- **Config always wins a triple collision, regardless of write order** — seed inserts use `ON CONFLICT DO NOTHING`, so they can never overwrite an existing row no matter that row's current `source`; config's own load uses `ON CONFLICT DO UPDATE`, so it always asserts itself. Even in the edge case where a seed write somehow reaches the table before startup config load completes, the config load's own upsert corrects the row's `source` back to `config`. The invariant holds by conflict-strategy construction, not by relying on load-order timing.
- Config parsed once at startup via `Settings`, not read inline.
- Turns 6.1.1's tests green — introduces no new contract beyond what 6.1.1 already pinned.

## Verification

- 6.1.1's red test suite passes green against this implementation.
- A configured edge `a/x > a/y : contract` loads at startup; `neighbors("a/x")` returns `["a/y"]` and `edges_from("a/x")` returns the typed `Edge`.
- Re-loading the same configured edge is idempotent (no duplicate).
- A seed write colliding with that configured edge's triple leaves it unchanged (`source` still `config`).
