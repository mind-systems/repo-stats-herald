# Test Plan: ServedRepoStore

## Context
`ServedRepoStore` (`src/ingestion/served_repos.py`) is the authoritative set of `(org_id, repo)` pairs the reporting run iterates, written by the installation-event branch and read by `scripts/report.py`. Nothing tests it today; the highest-value risk is an over-broad `remove` that silently drops another org's repos with no error and no log line.

## Settings
- Testing: yes
- Logging: minimal
- Docs: no

## Test Command
`uv run pytest tests/ingestion/test_served_repos.py`

## Target Spec File
`tests/ingestion/test_served_repos.py`

## Fixtures (extend existing file: `tests/ingestion/conftest.py`)
**`tests/ingestion/conftest.py` already exists** (~284 lines, created by the episodic-writer test task). It defines `events`, `mirror`, `embedder`, a `store` fixture returning a `FakeStore`, and the `make_*` builders that `test_episodic_writer.py` depends on pervasively. This is an **existing file to extend**, not a new file — the spec's "currently has no conftest" line is stale ground truth and the code wins.

Add the Postgres fixtures alongside the existing ones, following `tests/graph/conftest.py`'s settled non-vector, plain-table shape:
- `_dsn()` — module-level helper reading `POSTGRES_HOST`/`POSTGRES_PORT`/`POSTGRES_USER`/`POSTGRES_PASSWORD`/`POSTGRES_DB` with the `localhost` / `5432` / `herald_username` / `herald_password` / `herald_database` defaults.
- `SCHEMA_PATH = Path(__file__).resolve().parents[2] / "src" / "ingestion" / "schema.sql"`.
- `pg_pool` — async fixture: `await create_pool(_dsn())`, execute the schema text, then `TRUNCATE served_repos` (at setup, not teardown), `yield pool`, `await pool.close()`. Safe to add — no existing `pg_pool` definition.
- `served_store` — sync fixture returning `ServedRepoStore(pg_pool)`. **Do NOT name it `store`** — that name is already bound to the `FakeStore` fixture and rebinding it would feed a `ServedRepoStore` into `test_episodic_writer.py`, breaking every `store.entries` access. Every case in Tasks 1–6 requests `served_store`.

Notes:
- These are real-Postgres contract tests — a live database at the `_dsn()` defaults is required, same as `tests/graph`. Additions are additive only; they must not redefine any existing fixture name in this conftest (`store`, `events`, `mirror`, `embedder`, `make_*`) nor the root fixtures (`client`/`sign`/`push_payload`/`TEST_ORG_ID`) inherited from `tests/conftest.py`.
- Every `remove` case populates a second org in the background so an over-broad `WHERE` fails the assertion rather than passing on a single-tenant fixture.

## Tasks

### Phase 1: ServedRepoStore.add — insertion and idempotence

- [x] **Task 1: `add()` behavior**
  Files: `tests/ingestion/test_served_repos.py`
  Test cases:
  - `should record every (org_id, repo) pair when given a fresh list of repos`
  - `should leave the set unchanged when the same repos are added a second time` (ON CONFLICT DO NOTHING; a re-delivered `installation_repositories` must not raise UniqueViolationError)
  - `should insert only the new repos when the batch partially overlaps the existing set`
  - `should record the pair once when the same repo appears twice inside a single batch`
  - `should keep both rows when two different orgs add a repo with the same name` (composite PK — a PK on `repo` alone would swallow the second org's row)
  - `should store a large org_id losslessly when the org id exceeds 32 bits` (bigint column; use a value strictly above 2³¹ such as `2**32 + 7` — `TEST_ORG_ID = 244165546` is below 2³¹ and would pass even against a mistaken `integer` column, so it does not prove `bigint`)

- [x] **Task 2: `add()` guards and iterable contract**
  Files: `tests/ingestion/test_served_repos.py`
  Test cases:
  - `should be a no-op when the repos iterable is empty` (the `if not rows: return` guard — the hot path for every pure-removal installation event; assert no exception and `all()` unchanged)
  - `should consume a one-shot generator correctly when repos is a generator rather than a list` (pins single-pass materialization so a future double-iteration refactor fails loudly)

### Phase 2: ServedRepoStore.remove — org-scoped deletion

- [x] **Task 3: `remove()` org isolation and scoping**
  Files: `tests/ingestion/test_served_repos.py`
  Test cases:
  - `should leave another org's identically-named repo intact when removing one org's repo` (highest-value: guards the `org_id = $1` predicate against a cross-tenant delete)
  - `should delete only the named repos when other repos exist for the same org`
  - `should delete the intersection when the batch mixes present and absent repos`
  - `should remove nothing when the repo is not in the set for that org` (tolerance of a stale/replayed `repositories_removed`)
  - `should leave the org's other repos intact when removing every repo it currently has` (drain one org to empty while a second org still has rows)

- [x] **Task 4: `remove()` guards and iterable contract**
  Files: `tests/ingestion/test_served_repos.py`
  Test cases:
  - `should be a no-op when the repos iterable is empty` (the `if not repos: return` guard — the router calls `remove(org_id, ())` on every install-create; second org populated, assert it survives)
  - `should accept a generator when repos is not a list` (the `list(repos)` normalization; without it asyncpg receives an unencodable generator for the `text[]` parameter)

### Phase 3: ServedRepoStore.all — ordering and return shape

- [x] **Task 5: `all()` return contract**
  Files: `tests/ingestion/test_served_repos.py`
  Test cases:
  - `should return an empty list when the table is empty` (pins `[]` not `None` so the report loop degrades to zero iterations)
  - `should return (org_id, repo) tuples in that exact positional order` (assert `isinstance(pair[0], int)` and `isinstance(pair[1], str)` — a swapped mapping would still typecheck and feed a repo name into the org slot)
  - `should return 2-tuples, not asyncpg Record objects` (a raw Record destructures identically but leaks a connection-bound type past the pool)
  - `should order by org_id then repo when rows are inserted out of order` (the `ORDER BY org_id, repo` clause; insert deliberately out of order and assert the sorted result)
  - `should return every org's pairs when multiple orgs are served` (the deliberately unscoped SELECT)

### Phase 4: Convergence under replayed events

- [x] **Task 6: order-independence and concurrency**
  Files: `tests/ingestion/test_served_repos.py`
  Test cases:
  - `should converge to the same set when add and remove for one org are applied in either order` (`add(1,["a"])`→`remove(1,["b"])` and the reverse both yield `[(1,"a")]`)
  - `should yield the documented result for each ordering when add and remove target the same repo` (the genuinely order-dependent pair — do NOT assert convergence; assert each ordering's actual result so the distinction is documented)
  - `should reach the seeded state when an installation-create seed is replayed over an already-populated org` (`add` as the full-repository-list seed path)
  - `should apply concurrent adds for one org without error when awaited via asyncio.gather` (each `add` acquires its own connection, so this genuinely races at the DB; follow the `import asyncio` precedent in `tests/graph/test_project_graph_contract.py`)

## Out of scope
The router's installation branch (`router.receive_github_webhook`, `_parse_installation_event`) is a separate concern per the task and stays out of this plan.
