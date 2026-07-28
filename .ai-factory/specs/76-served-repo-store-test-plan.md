# ServedRepoStore — Test Plan

**Date:** 2026-07-29
**Source:** roadmap-test-coverage agent

## Source Overview

`ServedRepoStore` (`src/ingestion/served_repos.py`) is a thin asyncpg-backed wrapper over the `served_repos` table — the authoritative set of `(org_id, repo)` pairs Herald currently reaches. It has three methods: `add` (batched `executemany` of `INSERT INTO served_repos (org_id, repo) VALUES ($1, $2) ON CONFLICT DO NOTHING`), `remove` (`DELETE FROM served_repos WHERE org_id = $1 AND repo = ANY($2::text[])`), and `all` (`SELECT org_id, repo ... ORDER BY org_id, repo`, mapped to `list[tuple[int, str]]`). It is written by the installation-event branch of `src/ingestion/router.py` and read by the reporting run in `scripts/report.py` (`for org_id, repo in await served.all():`).

Schema (`src/ingestion/schema.sql`, the whole file):

```sql
CREATE TABLE IF NOT EXISTS served_repos (
    org_id bigint NOT NULL,
    repo   text   NOT NULL,
    PRIMARY KEY (org_id, repo)
);
```

The composite primary key is what makes `ON CONFLICT DO NOTHING` idempotent and what makes cross-org repo-name collisions legal — both are load-bearing for the tests below.

## Instantiation

Follow **`tests/graph/conftest.py`** exactly — it is the closest match (non-vector store, plain table, no embedding dimension to fake). `tests/knowledge/conftest.py` is the same shape; `tests/episodic/conftest.py` is the same shape plus a large unrelated git-fixture tail. All three are byte-identical in their `_dsn()` / `pg_pool` / `store` block, so the pattern is settled:

- `_dsn()` — module-level helper reading `POSTGRES_HOST`/`POSTGRES_PORT`/`POSTGRES_USER`/`POSTGRES_PASSWORD`/`POSTGRES_DB` with the `herald_username` / `herald_password` / `herald_database` / `localhost:5432` defaults.
- `SCHEMA_PATH = Path(__file__).resolve().parents[2] / "src" / "ingestion" / "schema.sql"`.
- `pg_pool` — async fixture: `await create_pool(_dsn())` from `src.core.db`, execute the schema text, then `await conn.execute("TRUNCATE served_repos")`, `yield pool`, `await pool.close()`.
- `store` — sync fixture returning `ServedRepoStore(pg_pool)`.

New file: `tests/ingestion/conftest.py` (the directory currently has no conftest; it inherits `client` / `sign` / `push_payload` / `TEST_ORG_ID` from `tests/conftest.py`). Adding an ingestion-level conftest is additive — it must not shadow those root fixture names. `asyncio_mode = "auto"` is set in `pyproject.toml`.

## Existing Coverage

**None for this store.** `tests/ingestion/test_webhook_contract.py` covers only the push branch and signature rejection: valid push, `refs/heads/feature/x` stripping, tampered signature, absent signature, and `test_non_push_event_is_ignored` — which sends `X-GitHub-Event: ping`, not `installation` or `installation_repositories`. The router's installation branch, `_parse_installation_event`, and every line of `served_repos.py` are untested. `grep -rn "ServedRepoStore\|served_repos" tests/` returns nothing.

## Test Cases

### `add()`

- **should record every `(org_id, repo)` pair when given a fresh list of repos** — `add` + `all`.
- **should leave the set unchanged when the same repos are added a second time** — `add` idempotence (`ON CONFLICT DO NOTHING`). This is the re-delivery case the spec pins: GitHub retries an `installation_repositories` delivery, and a non-idempotent insert would raise a `UniqueViolationError` and 500 the webhook, or in a laxer schema silently duplicate.
- **should insert only the new repos when the batch partially overlaps the existing set** — `add`. Guards against an all-or-nothing conflict policy that would drop the new repo because another collided.
- **should be a no-op when the repos iterable is empty** — the `if not rows: return` guard. Non-obvious: the router hits this on *every* `installation_repositories` event carrying only removals, and on every non-`created` `installation` action. Assert no exception and `all()` unchanged; ideally also assert no connection was acquired.
- **should consume a one-shot generator correctly when repos is a generator rather than a list** — `add`'s `Iterable[str]` contract. `add` materializes into `rows` in one pass; the test pins it so a future refactor that iterates `repos` twice fails loudly instead of silently inserting nothing.
- **should keep both rows when two different orgs add a repo with the same name** — `add` against the composite PK. A PK mistakenly declared on `repo` alone would silently swallow the second org's row.
- **should record the pair once when the same repo appears twice inside a single batch** — `executemany` sends each row as a separate statement, so the conflict is real and self-inflicted.
- **should store a large `org_id` losslessly when the org id exceeds 32 bits** — against the `bigint` column. Use the real `TEST_ORG_ID = 244165546` from `tests/conftest.py`, or a value above 2^31.

### `remove()`

- **should delete only the named repos when other repos exist for the same org** — `remove`.
- **should leave another org's identically-named repo intact when removing one org's repo** — `remove`'s `org_id = $1 AND ...` scoping. **This is the highest-value test in the plan.** A `WHERE repo = ANY($2)` that lost its `org_id` predicate deletes other tenants' rows with no error and no log line; the only symptom is those orgs silently vanishing from the next reporting run.
- **should remove nothing when the repo is not in the set for that org** — tolerance of a stale/replayed `repositories_removed`.
- **should be a no-op when the repos iterable is empty** — the `if not repos: return` guard. The router calls `remove(org_id, ())` on *every* `installation` create event.
- **should delete the intersection when the batch mixes present and absent repos** — `remove`.
- **should accept a generator when repos is not a list** — `remove`'s `list(repos)` normalization; without it, asyncpg would receive an unencodable generator for the `text[]` parameter.
- **should leave the org's other repos intact when removing every repo it currently has** — `remove` down to an empty per-org set while a second org still has rows.

### `all()`

- **should return an empty list when the table is empty** — pins `[]`, not `None`, so the `for org_id, repo in await served.all()` loop in `scripts/report.py` degrades to zero iterations rather than raising.
- **should return `(org_id, repo)` tuples in that exact positional order** — the row-to-tuple mapping. Non-obvious and critical: the reporting loop destructures positionally, so a swapped `return [(row["repo"], row["org_id"]) ...]` would still typecheck at runtime and silently feed a repo name into `mirror.ensure(repo, org_id)`'s org slot. Assert `isinstance(pair[0], int)` and `isinstance(pair[1], str)` explicitly.
- **should return 2-tuples, not asyncpg `Record` objects** — a `Record` destructures identically in the report loop, so a regression that returned raw rows would pass a naive equality test while leaking a connection-bound type past the pool's lifetime.
- **should order by `org_id` then `repo` when rows are inserted out of order** — the `ORDER BY org_id, repo` clause the docstring calls "stable, idempotent iteration." Without it, Postgres heap order is arbitrary and the reporting run's delivery order drifts between runs.
- **should return every org's pairs when multiple orgs are served** — `all`'s deliberately unscoped `SELECT`.

### Convergence / event-replay behavior (spec §Guards)

- **should converge to the same set when add and remove for one org are applied in either order** — Spec 36 pins "concurrent or replayed `installation_repositories` events for the same org need no explicit ordering." Two sub-cases, and they are *not* symmetric: `add(1,["a"])` → `remove(1,["b"])` vs. `remove(1,["b"])` → `add(1,["a"])` must both yield `[(1,"a")]`. Note the genuinely order-dependent pair (`add` then `remove` of the *same* repo vs. the reverse) is **not** convergent by design — do not assert it converges; assert each ordering's actual result so the distinction is documented.
- **should reach the seeded state when an installation-create seed is replayed over an already-populated org** — `add` as the "seed the full repository list" path.
- **should apply concurrent adds for one org without error when awaited via `asyncio.gather`** — under pool concurrency. Follow the `import asyncio` precedent already in `tests/graph/test_project_graph_contract.py`. Each `add` acquires its own connection from the pool, so this genuinely races at the DB.

### Router integration (optional, only if the installation branch is in scope)

- **should call `add` with the parsed `repositories_added` when an `installation_repositories` event arrives for a served org** — `router.receive_github_webhook` + `_parse_installation_event`. **Non-obvious setup, and this is why it is optional:** `tests/conftest.py`'s `client` fixture builds `TestClient(app)` *without* entering it as a context manager, so the `lifespan` never runs and `app.state.served_repo_store` is never set. The router reads it as a bare attribute, not via `getattr(..., None)` like the push collaborators — so this test must assign a fake or real store onto `app.state` before posting. Payload shape: `{"installation": {"account": {"id": TEST_ORG_ID}}, "repositories_added": [{"name": "alpha"}], "repositories_removed": []}`, signed with the `sign` fixture, `X-GitHub-Event: installation_repositories`, expect `204`.
- **should touch the store not at all when the installation event's org is outside the serve allowlist** — the allowlist gate. Spec 36's third verification bullet.
- **should seed the full `repositories` list when an `installation` event has `action: "created"`** — `_parse_installation_event`'s `installation` branch. Assert the reverse too: `action: "deleted"` yields empty added/removed tuples, which is exactly why `add`/`remove` need their empty-iterable guards tested above.

## Gotchas

- **Cross-org isolation is the silent failure.** Nothing in `served_repos` is per-tenant-scoped except the `org_id = $1` predicate in `remove` and the composite PK. Every `remove` test should be written with a second org populated in the background, so an over-broad `WHERE` fails the assertion rather than passing on a single-tenant fixture.
- **Empty iterables are the common case, not the edge case.** The router calls `store.add(org_id, ())` on every pure-removal event and `store.remove(org_id, ())` on every install-create, and `_parse_installation_event` returns `((), ())` for every `installation` action other than `created`. Both early-return guards are hot paths. Test both.
- **The schema is created by the app, not by a migration tool.** `src/main.py` executes `src/ingestion/schema.sql` inside `lifespan`, and `scripts/report.py` re-executes the same file. The test fixture must therefore read and execute that same `schema.sql` itself (as `tests/graph/conftest.py` does with `src/graph/schema.sql`). Because the file is `CREATE TABLE IF NOT EXISTS`, executing it per-test is safe; the `TRUNCATE served_repos` after it is what provides isolation.
- **These are real-Postgres contract tests, not mocked.** They require a live database at the `_dsn()` defaults, same as `tests/graph`, `tests/knowledge`, and `tests/episodic`. There is no in-memory fallback in this repo and inventing one would break the pattern.
- **`TRUNCATE` runs at fixture setup, not teardown**, in all three sibling conftests. Preserve that ordering so a failed test leaves its rows behind for inspection.
- **`tests/ingestion/` currently has no `conftest.py`.** Adding one is the intended move, but `test_webhook_contract.py` and `test_release_delivery.py` live in the same directory and inherit `client`/`sign`/`push_payload` from the root `tests/conftest.py`. Adding a `pg_pool` fixture there is additive and safe; redefining any root fixture name is not.
- **`add` uses `executemany`, which is not a single atomic statement.** A partial failure mid-batch can leave some rows inserted. Not worth a dedicated test, but do not write an assertion that assumes all-or-nothing batch semantics.
