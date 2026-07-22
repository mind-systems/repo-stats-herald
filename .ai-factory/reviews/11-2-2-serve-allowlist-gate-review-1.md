# Code Review — 2.2 Serve-allowlist gate

**Plan:** `.ai-factory/plans/11-2-2-serve-allowlist-gate.md`
**Spec:** `.ai-factory/specs/02-serve-allowlist-gate.md`
**Changed code:** `src/core/config.py`, `src/ingestion/router.py`, `tests/conftest.py`

## Scope

Reviewed `git diff HEAD` in full and read each changed file in its entirety plus its surroundings (`src/ingestion/models.py`, `src/main.py`, `tests/ingestion/test_webhook_contract.py`). The diff also carries planning artifacts (`.md`/`.json` under `.ai-factory/`) — no runtime surface, not reviewed for bugs.

## Verification performed

- **Allowlist parsing (`Settings.serve_allowlist`)** — exercised every spec case empirically against the pinned `pydantic-settings` with `NoDecode` in place:
  - `"244165546"` → `frozenset({244165546})`
  - `"244165546,244165547"` (multi-id) → `frozenset({244165546, 244165547})` — no `SettingsError` (the round-1 plan defect is resolved)
  - `""` → `frozenset()` (fail-closed, per spec Guards)
  - `" , "` (whitespace/empty tokens) → `frozenset()`
  - `"  244165546 , 244165547 "` (padded) → `frozenset({244165546, 244165547})`
  - unset → `frozenset()` (default; validator not run on default, which is already a frozenset)
- **Gate behavior end-to-end** via `TestClient` with a valid HMAC signature:
  - served org `244165546` → **200** (proceeds to the `JSONResponse` echo)
  - unlisted org `999999` → **204** (dropped, no downstream) — the path no automated test covers, confirmed manually
- **Existing contract suite** — `pytest tests/ingestion/test_webhook_contract.py` → **5 passed**. The two 200-asserting tests stay green because `conftest.py` now sets `SERVE_ALLOWLIST=str(TEST_ORG_ID)`; the 401/204 tests return before the gate and are unaffected.

## Correctness assessment

- **Ordering (`router.py`)** — the gate sits after signature verification (401), after the non-`push` → 204 short-circuit, and after `_parse_push_event`, then before the `JSONResponse`. Unverified/non-push requests never reach it; the drop is cheap (no token, no processing) as the spec requires.
- **Numeric comparison** — `event.org_id` is `int` on `PushEvent` and `serve_allowlist` is `frozenset[int]`; the check compares the rename-proof numeric id, not `org_login`. Matches the spec guard.
- **Single config read** — `settings = get_settings()` is bound once and both `github_webhook_secret` and `serve_allowlist` read from it; no inline env access. Consistent with the "config read once at the root and injected" pattern.
- **Fail-closed** — an empty or unset allowlist yields `frozenset()`, so `org_id not in frozenset()` is always true and every push is dropped. Never defaults to serve-all.
- **Validator robustness** — pass-through for set/frozenset inputs, split/strip/skip-empty/`int` for strings. A genuinely malformed token (e.g. `SERVE_ALLOWLIST=abc`) raises at `get_settings()` — a loud startup failure on misconfiguration, which is the desirable behavior for a security allowlist, not a defect.
- **Logging** — module-level logger, `info` level, single structured line naming `org_id` and `repo`; no `print`, no secret material logged.

## Findings

None. The implementation matches the spec on every pinned case (served proceeds, unlisted → 204, empty → all dropped, numeric id), the round-1 plan defect (`NoDecode`) is correctly applied and verified, and both the served and dropped paths behave as specified at runtime.

REVIEW_PASS
