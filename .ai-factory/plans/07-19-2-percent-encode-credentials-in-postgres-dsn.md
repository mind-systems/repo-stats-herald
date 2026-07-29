# Plan: 19.2 — Percent-encode credentials in `postgres_dsn`

## Context
Percent-encode the user and password components before interpolating them into the Postgres DSN, so a credential containing a URL-reserved character (`@`, `:`, `/`, `#`, `?`, …) yields a parseable DSN addressing the correct host. The same latent defect lives in one production path and four test-fixture mirrors (`tests/episodic`, `tests/graph`, `tests/knowledge`, `tests/ingestion` — each a byte-identical `_dsn()` helper building its own pool via `create_pool(_dsn())`) and all five move together as one concern.

## Settings
- Testing: no
- Logging: minimal
- Docs: no

## Tasks

### Phase 1: Encode credentials in the production DSN and its four fixture mirrors

- [x] **Task 1: Encode credentials in `Settings.postgres_dsn`**
  Files: `src/core/config.py`
  In the `postgres_dsn` property (currently lines 106–111), percent-encode both `postgres_user` and `postgres_password` before interpolation, leaving `postgres_host`, `postgres_port`, and `postgres_db` untouched. Use `urllib.parse.quote(value, safe="")` (add the `from urllib.parse import quote` import at the top of the module alongside the existing `json`/`dataclasses`/`functools` imports). Applying `quote(..., safe="")` to each credential and interpolating the results keeps the DSN byte-identical for the current defaults (`herald_username` / `herald_password` contain only characters `quote` leaves untouched), satisfying the guard that no existing environment's connection string changes; only genuinely reserved characters get escaped.

- [x] **Task 2: Encode credentials in the episodic test fixture `_dsn` helper**
  Files: `tests/episodic/conftest.py`
  In the `_dsn()` helper (lines 22–28), apply the same `urllib.parse.quote(value, safe="")` encoding to the `user` and `password` values before building the `postgresql://…` string, mirroring Task 1 exactly. Add `from urllib.parse import quote` to the module imports. Host, port, and db stay unencoded. This fixture builds its own pool via `create_pool(_dsn())`, so its DSN must match the production path's encoding to stay in step.

- [x] **Task 3: Encode credentials in the graph test fixture `_dsn` helper**
  Files: `tests/graph/conftest.py`
  In the `_dsn()` helper (lines 15–21), apply `urllib.parse.quote(value, safe="")` to `user` and `password` before interpolation, identical to Tasks 1–2. Add the `from urllib.parse import quote` import. Host/port/db unchanged.

- [x] **Task 4: Encode credentials in the knowledge test fixture `_dsn` helper**
  Files: `tests/knowledge/conftest.py`
  In the `_dsn()` helper (lines 16–22), apply `urllib.parse.quote(value, safe="")` to `user` and `password` before interpolation, identical to Tasks 1–3. Add the `from urllib.parse import quote` import. Host/port/db unchanged.

- [x] **Task 5: Encode credentials in the ingestion test fixture `_dsn` helper**
  Files: `tests/ingestion/conftest.py`
  In the `_dsn()` helper (lines 23–29), apply `urllib.parse.quote(value, safe="")` to `user` and `password` before interpolation, identical to Tasks 1–4. Add the `from urllib.parse import quote` import. Host/port/db unchanged. This fixture builds its own pool via `create_pool(_dsn())` (line 303), so its DSN must match the production path's encoding to stay in step.
