# Code Review: 2.1.2 — Signed webhook receipt (impl)

**Reviewed:** `src/ingestion/router.py` (the only production change)
**Against:** `.ai-factory/specs/01-signed-webhook-receipt.md`, `src/ingestion/models.py`, `src/core/config.py`, `tests/conftest.py`, `tests/ingestion/test_webhook_contract.py`
**Suite:** `uv run pytest tests/ingestion/test_webhook_contract.py` → **5 passed**.

The implementation matches the plan and spec: raw body is read before any parse, HMAC is compared with `hmac.compare_digest` against `X-Hub-Signature-256`, non-`push` events short-circuit to 204, and the verified payload maps correctly onto the existing `PushEvent`/`PushCommit` value objects (`id`→`sha`, `author.name`→`author`, `refs/heads/` stripped, numeric `org_id`). Verify-before-parse ordering, constant-time comparison, empty 401 body, and secret-from-env-via-`Settings` are all honored. One low-severity finding below.

## Findings

### 1. [Low] Malformed (non-ASCII) signature header returns 500, not the spec's 401

`src/ingestion/router.py:20` — `hmac.compare_digest` raises `TypeError` ("comparing strings with non-ASCII characters is not supported") when the header value contains any non-ASCII character. HTTP header values are not ASCII-guaranteed: over the wire, Starlette/uvicorn decode raw header bytes as latin-1, so a client sending `X-Hub-Signature-256: sha256=<byte 0x80–0xFF>` reaches the handler as a non-ASCII `str`, and `_verify_signature` raises an unhandled `TypeError` → HTTP **500**.

The spec's guard states: *"Missing/malformed/mismatched signature → `401`, nothing parsed."* A non-ASCII signature is malformed and should yield 401, not a 500.

**Reproduced** (raw ASGI request with header byte `0xe9`):
```
header seen by handler: 'sha256=café'
UNHANDLED: TypeError comparing strings with non-ASCII characters is not supported
```
(The 2.1.1 test suite does not catch this because its `httpx`-based `TestClient` normalizes outgoing header values to ASCII on the client side, so the malformed-header case never leaves the test client — it only occurs against a real server.)

**Severity rationale:** low, and it fails *closed* — no body is parsed and no processing occurs, so there is no verification bypass. The impact is a wrong status code (500 vs 401) and an unhandled exception logged as a server error on malformed attacker input.

**Suggested fix** — treat a non-ASCII/comparison-failure header as a failed verification:
```python
def _verify_signature(body: bytes, header: str | None, secret: str) -> bool:
    if header is None:
        return False
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    try:
        return hmac.compare_digest(expected, header)
    except TypeError:
        return False
```

## Notes (no action required)

- **Request-time `get_settings()`** (`router.py:50`) is correct here, not an architecture violation: the 2.1.1 contract (`webhook_secret_env` in `tests/conftest.py`) monkeypatches the env and calls `get_settings.cache_clear()` per test against a module-level `app`, so the secret must be resolved per request. It reads via `Settings`, satisfying the spec's "secret only from env via `Settings`" guard.
- **Post-verification `KeyError`/`json.loads` on a malformed-but-signed body** would 500, but the body is authenticated (signed with Herald's secret) and GitHub org push payloads always carry these fields — consistent with the phase's org-scoped design. Out of scope for this task; noted only for traceability.
- **Serialization** via `JSONResponse(content=jsonable_encoder(event))` correctly renders the frozen/slotted dataclasses with tuples → JSON arrays; returning a `Response` subclass under the `-> Response` annotation bypasses response_model coercion. Sound.
