# Code Review (Re-review): 2.1.2 — Signed webhook receipt (impl)

**Reviewed:** `src/ingestion/router.py` (only production change)
**Against:** previous review `.ai-factory/reviews/10-2-1-2-signed-webhook-receipt-impl-review-1.md`, `.ai-factory/specs/01-signed-webhook-receipt.md`, `src/ingestion/models.py`, `src/core/config.py`, `tests/conftest.py`, `tests/ingestion/test_webhook_contract.py`
**Suite:** `uv run pytest tests/ingestion/test_webhook_contract.py` → **5 passed**.

## Verdicts on prior findings

### 1. [Low] Malformed (non-ASCII) signature header returns 500, not the spec's 401 — **Fixed**

Current content of the cited function (`src/ingestion/router.py:16-23`):
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

The `try/except TypeError: return False` now wraps `hmac.compare_digest`, so a non-ASCII header value (which `compare_digest` rejects with `TypeError`) is treated as a failed verification rather than propagating. Re-reproduced end-to-end via a raw ASGI request carrying header byte `0xe9` (`sha256=café`) — the handler now returns **401** (previously an unhandled `TypeError` → 500):
```
non-ASCII header status: 401
```
This matches the spec guard "Missing/malformed/mismatched signature → 401, nothing parsed" and still fails closed (no parse, no processing). Fixed.

## New review

Full re-read of `src/ingestion/router.py`; `git diff HEAD` shows the router as the sole production change. No new issues found.

- Verify-before-parse ordering intact: raw `body` read (`:52`), signature checked (`:55`), non-`push`→204 gate (`:58`), parse only after both pass (`:61`).
- Constant-time comparison preserved (`hmac.compare_digest`), header-absent short-circuits to `False` before any comparison, 401 responses carry no body (`test_tampered_signature_is_rejected`'s `"branch" not in response.text` holds).
- Payload mapping unchanged and correct against the `push_payload` fixture (`id`→`sha`, `author.name`→`author`, `refs/heads/` stripped, numeric `org_id` from `organization.id`, tuples for `added/modified/removed/commits`).
- Secret resolved per request via `get_settings()` (required by the per-test `cache_clear()` contract) and only through `Settings` — satisfies the "secret from env only" guard.
- `JSONResponse(content=jsonable_encoder(event))` serializes the frozen/slotted dataclasses (tuples → JSON arrays); returning a `Response` subclass under `-> Response` bypasses response_model coercion. Sound.

The one carried-over non-blocking note (post-verification `KeyError`/`json.loads` on a signed-but-malformed body would 500) remains out of scope: the body is authenticated and org-scoped GitHub push payloads always carry these fields. No action needed for this task.

REVIEW_PASS
