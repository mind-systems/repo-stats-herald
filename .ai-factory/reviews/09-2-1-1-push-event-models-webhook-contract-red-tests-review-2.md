# Code Review (re-review): 2.1.1 — Push-event models + webhook contract (red tests)

Re-review after fixes for `review-1.md`. Verdicts on each prior finding (files re-read fresh, not from memory), then a full pass for new issues.

## Prior findings

### Low — inconsistent test-package layout (conftest double-import + latent prepend-mode collision) → **Fixed**

`review-1` flagged that `tests/__init__.py` was absent while `tests/ingestion/__init__.py` was present and `test_webhook_contract.py` did `from tests.conftest import …`, causing `conftest.py` to load twice and setting up a future pytest prepend-mode name collision.

Current state — `tests/__init__.py` now exists (`git status`: `A  tests/__init__.py`), read fresh and confirmed empty:

> *(the file exists but the contents are empty)*

Evidence the layout is now sound:
- `import tests, tests.ingestion` → `tests is regular pkg: True`, `tests.ingestion is regular pkg: True` (both have `__file__`, so they are real packages, not namespace packages). The test module now imports as `tests.ingestion.test_webhook_contract`, so `from tests.conftest import TEST_ORG_ID, TEST_ORG_LOGIN` (`test_webhook_contract.py:9`) is a single ordinary import — no second `conftest` load, no basename-collision trap for future test packages.

Verdict: **Fixed** with the minimal, recommended change.

## Full re-review (all changed files re-read in full)

Only `tests/__init__.py` was added since review-1; every other file is byte-identical to the version I already validated. Re-verified regardless:

- **`src/ingestion/models.py`** — `PushCommit`/`PushEvent` frozen `slots` dataclasses, fields match the spec exactly; `org_id: int` vs `org_login: str` preserved.
- **`src/ingestion/router.py`** — `POST /webhooks/github` returns an explicit `Response(status_code=501)`; no logic, no settings read. Correct stub.
- **`src/main.py`** — `app.include_router(ingestion_router)`; `/health` intact.
- **`src/core/config.py`** — `github_webhook_secret: str` required, no default; nothing instantiates `Settings` at import, so the web path stays boot-safe.
- **`pyproject.toml`** — `pytest` dev group; `[tool.pytest.ini_options]` carries `testpaths` **and** `pythonpath = ["."]` (the review-1 critical fix), so `src` resolves under any run form.
- **`Makefile`** — `test: uv run pytest`, `test` in `.PHONY`.
- **`tests/conftest.py`** — secret injected via `monkeypatch.setenv` + `get_settings.cache_clear()`; `sign()` produces the `sha256=<hmac-hex>` header shape; payload builder mirrors a real GitHub push.
- **`tests/ingestion/test_webhook_contract.py`** — five cases covering valid→200 (with `ref`→`branch` strip and numeric `org_id`), tampered→401, **absent**→401 (own test), signed non-`push`→204.

**Executed the suite:** `uv run pytest` → `5 failed, 1 warning`, every failure an `assert <expected> == 501` on the response status — red for the right reason, **no** collection/import/fixture errors. Exactly the task's guard.

No bugs, security issues, correctness problems, or runtime hazards found. The `StarletteDeprecationWarning` is pre-existing environment noise, not errored, unrelated to this change.

REVIEW_PASS
