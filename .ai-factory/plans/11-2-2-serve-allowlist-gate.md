# Plan: 2.2 — Serve-allowlist gate

## Context
Gate a verified `push` (2.1's `PushEvent`) on a fail-closed set of served GitHub org ids so Herald acts only on organizations it serves — an unlisted org is dropped cheaply (log + 204) before any token minting or downstream work.

## Settings
- Testing: no
- Logging: minimal
- Docs: no

## Tasks

### Phase 1: Settings — serve-allowlist

- [x] **Task 1: Add `Settings.serve_allowlist` as a parsed `frozenset[int]`**
  Files: `src/core/config.py`
  Add field `serve_allowlist: Annotated[frozenset[int], NoDecode] = frozenset()` to `Settings` (default empty = fail-closed, serves no one). The `NoDecode` marker is **required**: pydantic-settings treats `frozenset[int]` as a complex field and JSON-decodes the raw env string at the settings-source level *before* any validator runs, so without `NoDecode` a comma-separated multi-id value or an empty string raises `SettingsError` at `get_settings()` — a startup crash, not the fail-closed empty set the spec pins. `NoDecode` hands the raw string to the validator instead. Imports: `from typing import Annotated`, `from pydantic import field_validator`, and add `NoDecode` to the existing `from pydantic_settings import ...` line. Add a `@field_validator("serve_allowlist", mode="before")` that: returns the value unchanged if it is already a set/frozenset (so the default and in-code values pass through); otherwise treats it as a string, splits on `,`, strips each token, skips empty tokens, and parses each to `int`, returning a `frozenset[int]`. An empty or whitespace-only string yields `frozenset()` (fail-closed). Follow the existing module style — the field sits alongside `github_webhook_secret`; do not add env-reading logic anywhere else. `.env.example` already documents the `SERVE_ALLOWLIST` key, so no change there.

### Phase 2: Gate the verified push

- [x] **Task 2: Drop non-served orgs after parse in the webhook route** (depends on Task 1)
  Files: `src/ingestion/router.py`
  In `receive_github_webhook`, after `event = _parse_push_event(body)` and before the existing `JSONResponse` return, check `event.org_id not in settings.serve_allowlist`. On a miss: log at `info` (module-level `logging.getLogger(__name__)`) naming the numeric `org_id` and `repo` and that the org is "not served", then `return Response(status_code=204)` — no token, no further work. On a hit: fall through to the current behavior (the `JSONResponse` echo that 2.1.2 returns), which is where later phases attach downstream processing. Read the allowlist through `settings` (reuse the `get_settings()` call already made for `secret`, i.e. bind `settings = get_settings()` once and read both `settings.github_webhook_secret` and `settings.serve_allowlist` from it) — never read env inline. Comparison is on the numeric `org_id` (int), not `org_login`. Add the `logging` import at the top; keep the log message a single structured line (no `print`).

### Phase 3: Keep existing webhook tests green

- [x] **Task 3: Set `SERVE_ALLOWLIST` in the test env fixture** (depends on Task 1)
  Files: `tests/conftest.py`
  The two contract tests that assert `200` push through `TEST_ORG_ID = 244165546`; with the gate now fail-closed, an unset `SERVE_ALLOWLIST` would drop them to `204`. In the `webhook_secret_env` fixture (which already `monkeypatch.setenv` the secret and clears `get_settings.cache_clear()`), also `monkeypatch.setenv("SERVE_ALLOWLIST", str(TEST_ORG_ID))` so the served-org tests stay green and the gate reads the same org the payload carries. This only wires the existing fixture to the new setting — no new test cases are added.
