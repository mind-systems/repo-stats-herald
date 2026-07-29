# Plan: 19.1 — Scrub the bot token from delivery failure paths

## Context
`TelegramClient.send` must never let a token-bearing exception escape: both the non-2xx and the transport-failure paths raise a client-owned error whose message and attributes carry only the status code and a redacted endpoint, never the token or any `httpx` request/response object exposing it. The spec's Verification section (`.ai-factory/specs/56-telegram-token-redaction.md`) names three checks — stubbed 400, stubbed transport failure, unchanged happy path — so the existing test module is updated alongside the code.

## Settings
- Testing: yes — the guard "token absent from `str()`, `repr()`, and any reachable attribute" is a silent-failure surface (a leak passes tests today yet exposes the credential), so it must be asserted. Also, a pre-existing test in the touched module goes red under this change and must be repaired.
- Logging: minimal
- Docs: no

## Tasks

### Phase 1: Redact the failure paths

- [x] **Task 1: Add a client-owned error type**
  Files: `src/delivery/telegram.py`
  Define a module-level exception class (e.g. `TelegramSendError(Exception)`) that the client raises for any send failure. Follow the existing pattern of `CommitCollectionError` in `src/commits/collector.py` (a small subclass with a one-line docstring describing what it signals). Its constructed message contains only a fixed redacted endpoint string — `https://api.telegram.org/bot<redacted>/sendMessage` — and, when known, the HTTP status code. It stores the status code as an attribute (e.g. `status_code: int | None`) and the redacted endpoint (e.g. `endpoint: str`). It stores NO token, NO raw URL, and NO `httpx` request/response/exception object on any attribute — so that neither its `str()`/`repr()` nor any attribute reachable from it exposes the credential. Keep `TELEGRAM_MESSAGE_LIMIT` and the `TelegramClient` structure otherwise unchanged.

- [x] **Task 2: Catch both failure paths in `send` and re-raise redacted** (depends on Task 1)
  Files: `src/delivery/telegram.py`
  In `TelegramClient.send`, wrap the per-chunk `client.post(...)` + `response.raise_for_status()` in a `try` and translate both failure modes:
  - `httpx.HTTPStatusError` (raised by `raise_for_status()` on a non-2xx response) — extract only the primitive status code into a local: `status = exc.response.status_code if exc.response is not None else None` (guard against `exc.response` being `None`, so the block never `AttributeError`s before it can redact).
  - `httpx.RequestError` (transport failure — connection error, timeout, etc.; its `.request.url` carries the token) — set `status = None`.

  **Sever the exception chain by raising outside the `except` block.** This is the one detail that must be gotten exactly right. `raise TelegramSendError(...) from None` sets `__cause__ = None` and `__suppress_context__ = True`, but does NOT stop `__context__` from being populated: CPython re-sets `__context__` to the exception currently being handled *at the moment of `raise`*, so any `raise` inside the `except` block leaves `raised.__context__` pointing at the token-bearing `httpx` exception — and `raised.__context__.request.url` still carries the token, reachable from the raised error's attributes. Assigning `err.__context__ = None` before `raise err` does not help either: the `raise` overwrites it. The reliable fix is to leave the `except` block first (which clears the handler's active exception), then raise — so no implicit context is established and `__context__` is genuinely `None`:
  ```python
  async def send(self, chat_id: str, text: str) -> None:
      url = f"https://api.telegram.org/bot{self._token}/sendMessage"
      async with httpx.AsyncClient(timeout=self._timeout) as client:
          for chunk in self._chunks(text):
              try:
                  response = await client.post(url, json={"chat_id": chat_id, "text": chunk})
                  response.raise_for_status()
              except httpx.HTTPStatusError as exc:
                  status = exc.response.status_code if exc.response is not None else None
              except httpx.RequestError:
                  status = None
              else:
                  continue
              raise TelegramSendError(status)   # no active exception here → __context__ stays None
  ```
  `HTTPStatusError` is not a subclass of `RequestError`, so both `except` clauses are genuinely required. Do not build the redacted endpoint from `self._token` or the live `url`; the `TelegramSendError` constructor uses the fixed literal so the token cannot leak through string interpolation. The happy path (chunking via `_chunks`, chunk order, chunk JSON body, successful sends returning `None`) stays exactly as it is; `send` still raises on both failure modes, preserving the caller's signalling discipline (`DeliveryService.deliver` awaits `send` without catching a type; `src/ingestion/router.py` catches bare `except Exception` via `logger.exception` — `TelegramSendError` propagates and is handled exactly as the old exception was).

- [x] **Task 3: Repair and extend the client's tests** (depends on Tasks 1–2)
  Files: `tests/delivery/test_telegram_client.py`
  The existing `FakeResponse.raise_for_status` raises whatever error the test configures, so both failure modes are already stubbable through `_install_fake_transport(monkeypatch, error=...)`.
  - **Repair the pre-existing red test.** `test_bad_token_response_raises_and_is_not_swallowed` currently stubs `httpx.HTTPStatusError("Unauthorized", request=None, response=None)` and asserts `pytest.raises(httpx.HTTPStatusError)`. Under Task 2 `send` re-raises `TelegramSendError`, and `response=None` would otherwise trip the status-code read — so update the stub to carry a response with a status code (e.g. a tiny stand-in exposing `.status_code`, or `httpx.HTTPStatusError("Bad Request", request=<req with a token-bearing URL>, response=<resp with status_code=400>)`) and change the assertion to expect `TelegramSendError`. Assert the raised error's `str()` and `repr()` and every string attribute contain no token, and that `status_code == 400`. Give the stubbed `request` a URL containing the token so the "no token reachable" assertion is meaningful — including a check that no `__context__`/`__cause__` reachable from the raised error carries the token.
  - **Add the transport-failure case** (spec Verification item 2): stub a `httpx.ConnectError` whose `.request.url` carries the token, assert `send` raises `TelegramSendError` with `status_code is None`, and assert no token appears in its `str()`/`repr()`, its attributes, or anything reachable via `__context__`/`__cause__`.
  - The happy-path checks (`test_single_short_message_posts_exactly_once`, `test_over_length_message_splits_into_ordered_lossless_parts`) already cover spec Verification item 3 and stay unchanged.
