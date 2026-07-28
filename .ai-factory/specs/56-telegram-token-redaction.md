# 19.1 — Scrub the bot token from delivery failure paths

**Phase:** 19 — Boundary representation mismatches. Independent of 19.2, 19.3, and 19.4 — touches only the delivery client's failure handling.

## Current state

`TelegramClient.send` builds `https://api.telegram.org/bot{token}/sendMessage` and calls `response.raise_for_status()` on the result. Verified directly against httpx: the resulting `HTTPStatusError`'s string form contains that URL, token included. A transport failure's own message does not carry the URL, but every `httpx.RequestError` exposes `.request.url`, which does — and the path is already reachable today, not hypothetical: the Telegram send runs inside the release fan-out, which runs under the ingestion router's per-task isolation wrapper, and that wrapper catches with a bare `except Exception` and reports through `logger.exception`, which formats the exception and so writes the token to the log. The leak surface is the escaping exception object as a whole, not only the status-error message.

## Change

Let no token-bearing exception escape `send`. Catch both the non-2xx response path and the transport-failure path, and raise a client-owned error whose message and attributes carry no credential — the status code and a redacted form of the endpoint stay available for diagnosis, but neither the token nor a request object that exposes it is reachable from what `send` raises.

## Files & types

- edit `src/delivery/telegram.py` (`TelegramClient.send`)

## Guards

- `send` still raises on a non-2xx response and on a transport failure — the calling discipline established when this client was first built is unchanged, only what the raised error carries changes.
- The status code and a redacted form of the endpoint remain available on the raised error, so a failure is still diagnosable without the token.
- The token is absent from the raised error's `str()`, its `repr()`, and any request object reachable from its attributes.
- A successful send is unaffected — chunk ordering, chunk content, and the happy path stay exactly as they are.

## Verification

- A stubbed 400 response raises an error whose string form and attributes contain no token.
- A stubbed transport failure (connection error) raises an error whose string form and attributes contain no token.
- A successful send behaves identically to before this change.
