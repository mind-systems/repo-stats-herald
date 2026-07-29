## Code Review Summary

**Task:** 19.1 — Scrub the bot token from delivery failure paths
**Files reviewed (code):** `src/delivery/telegram.py`, `tests/delivery/test_telegram_client.py`
**Consulted:** `.ai-factory/specs/56-telegram-token-redaction.md`, the plan, `src/delivery/service.py`, `src/ingestion/router.py`
**Risk Level:** 🟢 Low — implementation matches the spec and plan; all guards verified at runtime.

### What changed
- `src/delivery/telegram.py`: added `TelegramSendError(Exception)` holding only `status_code: int | None` and a fixed redacted `endpoint` literal (`https://api.telegram.org/bot<redacted>/sendMessage`); no token, no `httpx` object. `TelegramClient.send` now wraps the per-chunk `post` + `raise_for_status()` in a `try`, extracts only the primitive status from `httpx.HTTPStatusError` (guarding `exc.response is None`), sets `status=None` on `httpx.RequestError`, uses `else: continue` on success, and raises `TelegramSendError(status)` *outside* the `except` block.
- `tests/delivery/test_telegram_client.py`: repaired the pre-existing bad-token test to expect `TelegramSendError` with a status-bearing stubbed response; added a transport-failure (`ConnectError`) case; both use a token-bearing request URL and assert via `_assert_no_token_reachable` (str, repr, every `vars()` attribute, `__cause__`, `__context__`). Happy-path tests unchanged.

### Verification performed
- `uv run pytest tests/delivery/test_telegram_client.py` → **4 passed**. The two failure tests assert `exc.__context__ is None` and `exc.__cause__ is None` and that the token appears in none of `str`/`repr`/attributes — so the round-2 leak (context re-populated at `raise` time) is confirmed closed at runtime by the raise-outside-`except` structure.
- Exception hierarchy confirmed against ground truth: `HTTPStatusError` is **not** a `RequestError` subclass (both clauses genuinely required), while `ConnectError`/`TimeoutException`/`TooManyRedirects` all are — so the single `RequestError` clause covers the transport-failure surface. `raise_for_status()` is the only source of `HTTPStatusError`. Both spec-named leak paths (non-2xx and transport) are covered.

### Guard-by-guard (spec `56-telegram-token-redaction.md`)
- "`send` still raises on both paths" — met; signalling discipline preserved. `DeliveryService.deliver` awaits without catching a type and `src/ingestion/router.py` catches bare `except Exception` via `logger.exception`, so `TelegramSendError` propagates and is handled as the prior exception was.
- "status + redacted endpoint remain available" — met (`status_code`, `endpoint`, message).
- "token absent from `str()`, `repr()`, and any reachable request object" — met and asserted; `__context__`/`__cause__` both `None`.
- "successful send unaffected (chunk order/content/happy path)" — met; `_chunks`, JSON body, and `None` return are untouched, and `else: continue` skips the raise on success.

### Notes (non-blocking, no action required)
- Exceptions outside the two clauses (e.g. `httpx.InvalidURL`) would propagate uncaught, but the endpoint is well-formed so they are not reachable here, and they are outside the spec's two named paths. No concern.
- On a multi-chunk send, a failing chunk raises immediately and skips remaining chunks — identical to the pre-change `raise_for_status()` behavior.

REVIEW_PASS
