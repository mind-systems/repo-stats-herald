# Code Review — 3.5 Installation-repositories tracking

**Plan:** `.ai-factory/plans/19-3-5-installation-repositories-tracking.md`
**Changed code files:** `src/ingestion/router.py`, `src/ingestion/models.py`, `src/ingestion/served_repos.py` (new), `src/ingestion/schema.sql` (new), `src/main.py`
**Risk Level:** 🟢 Low

## Summary

The implementation faithfully realizes the plan and closes the bug the task targets: the early non-`push`→204 return (which swallowed installation events) is gone, replaced by per-event dispatch that reaches the new `installation` / `installation_repositories` branch. Every pinned decision from the plan is honored:

- **Org identity** comes from `payload["installation"]["account"]["id"]` (router.py:54), the correct namespace for these events (push uses `organization.id`; both are the same int id space the `frozenset[int]` allowlist compares against).
- **Short repo name** (`r["name"]`) is stored, matching `_parse_push_event` and `RepoMirror`'s `{mirror_root}/{repo}.git` keying.
- **Only `installation` action `created`** seeds from `repositories`; every other installation action is a no-op (router.py:59‑64). No speculative purge-on-delete.
- **`ServedRepoStore`** is a single concrete class taking an injected `asyncpg.Pool`; SQL stays inside it; wired only in `main.py`'s lifespan (composition root). No speculative ABC.
- **Security order preserved:** HMAC verification is first (router.py:74), the allowlist gate returns `204` before any DB write (router.py:88‑90), matching push discipline exactly.
- **Idempotency is structural:** composite PK + `INSERT … ON CONFLICT DO NOTHING` + set-based `DELETE … = ANY($2::text[])` — concurrent/replayed events converge without ordering.

## Correctness checks

- **Dispatch restructure** — `event_name` read once; `push` runs the original parse/gate/response verbatim; `installation*` handled; all else falls to the tail `204`. The existing `ping`→204 contract test still holds via that tail. ✅
- **Test coexistence** — `tests/ingestion/test_webhook_contract.py` uses `TestClient(app)` without a `with` block, so lifespan never runs and `app.state.served_repo_store` is never needed by push/ping tests. Adding `lifespan=` does not break them; the installation branch (the only path touching the store) is not exercised by any existing test. ✅
- **`ServedRepoStore.add/remove`** — empty-iterable guards avoid no-op round-trips; `executemany` with `ON CONFLICT DO NOTHING` tolerates intra-payload duplicates; `repo = ANY($2::text[])` maps a Python `list[str]` correctly in asyncpg. ✅
- **Parse guards** — `repositories_added` / `repositories_removed` / `repositories` default to `[]`, so a payload missing a list never `KeyError`s. ✅
- **Schema** — `served_repos(org_id bigint, repo text, PRIMARY KEY (org_id, repo))`, idempotent `CREATE TABLE IF NOT EXISTS`, applied at startup from a file-relative path. `bigint` correctly accommodates GitHub account ids beyond 32-bit. ✅

## Non-blocking observations (no action required in this task)

- **App-wide startup now depends on Postgres + pgvector.** The lifespan opens the shared `create_pool`, whose `_init_connection` unconditionally registers the `vector` type codec (`src/core/db.py`). If Postgres is down or the `vector` extension is absent, the whole app fails to boot — including `/health` and the push webhook, which need no DB. This is an inherent consequence of the spec-mandated "reuse 3.3's asyncpg pool" at the single app root, and the extension is a documented per-machine prerequisite (`CLAUDE.md` first-time setup runs `CREATE EXTENSION IF NOT EXISTS vector`), so it is not a defect here. Worth keeping in mind when 3.6 wires the knowledge store into the same root — the `chunks` schema and the extension dependency should be made explicit there rather than relying on manual setup (matches the plan-review's deferred observation).
- **Pool not closed if schema execution raises at startup.** In `lifespan`, an exception from `conn.execute(SCHEMA_PATH.read_text())` propagates before `yield`, so the `await pool.close()` after `yield` never runs and the just-opened pool leaks. This only occurs on a startup failure where the process is aborting anyway, so the impact is negligible; a `try/except` around startup with `pool.close()` on failure would tidy it but is not necessary for correctness.

No correctness, security, or race-condition defects found. The two notes above are accepted design consequences / trivia, not actionable bugs in this task's scope.

REVIEW_PASS
