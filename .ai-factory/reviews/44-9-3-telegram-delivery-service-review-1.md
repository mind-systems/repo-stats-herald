# Code Review: 9.3 — Telegram delivery service

**Scope reviewed:** `src/core/config.py`, `src/routing/models.py`, `src/routing/resolver.py`, `src/delivery/service.py`, `tests/routing/test_role_for_branch.py`, `tests/delivery/test_delivery_service.py` (full files, not just diff).

## Verification performed
- **Tests run** (`uv run pytest tests/delivery/test_delivery_service.py tests/routing/test_role_for_branch.py`): **10 passed**.
- **Async convention:** `pyproject.toml` sets `asyncio_mode = "auto"`, so the marker-less `async def` delivery tests are genuinely collected and awaited — they are not silently skipped no-ops.
- **Numeric org-id key coercion (the one silent-failure hazard):** confirmed empirically. `Settings(..., telegram_channels='{"1": "-100123"}')` produces `{1: "-100123"}` with an **int** key; `.get(1)` → `"-100123"`, `.get("1")` → `None`. The str/int mismatch that would resolve every org to `None`/wrong chat cannot occur — and the test `test_telegram_channels_json_string_parses_to_int_keys` pins exactly this path (the dict-literal tests alone would have been a false positive, since a dict input bypasses the validator; the JSON-string test closes that gap).
- **Wiring:** `DeliveryPlan` is only ever constructed keyword-wise in `resolver.py`; the two new fields are defaulted and appended after the non-default fields, so dataclass field ordering is valid and no existing construction breaks. `DeliveryPlanResolver` is built at the composition root (`src/main.py:55`) from injected `Settings`. `DeliveryService` is intentionally un-wired — correct: transport only, first caller is the Phase 10 report.

## Correctness / security
No correctness or security issues found. The change matches the governing spec (`.ai-factory/specs/16-telegram-delivery.md`) point-for-point: reused `_parse_json_dict` (no invented delimited format), lowercase `"ru"` language matching `narrate`/localizer, single concrete class with no ABC, log-and-skip on unmapped org, and no `src/ingestion/router.py` edit (no per-push delivery). `TelegramClient.send` errors propagating on the mapped path is expected 9.2 transport behavior, not a regression; the spec's "never crashes" guard applies to the unmapped case, which is handled.

## Minor observations (non-blocking, no change required)
- `DeliveryService.deliver` logs `"no telegram channel resolved for this delivery, skipping"` without an org id. `DeliveryPlan` does not carry `org_id`, so it cannot log one — acceptable for this scope, but worth noting for observability when the Phase 10 caller lands.
- An empty-string channel in config (`""`) would pass the `is None` guard and attempt a send with an empty `chat_id`; Telegram would reject it. This is a config-error edge outside this task's scope and not a defect here.

REVIEW_PASS
