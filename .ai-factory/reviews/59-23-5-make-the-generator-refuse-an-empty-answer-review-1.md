# Code Review: 23.5 — Make the generator refuse an empty answer

**Files reviewed:** `src/llm/client.py`, `tests/llm/__init__.py`, `tests/llm/conftest.py`, `tests/llm/test_client.py`
**Verification:** ran `uv run pytest tests/llm/` → 15 passed; full suite `uv run pytest` → 216 passed.

## Summary

The change is small, correct, and well-targeted. `OllamaClient.generate` now decodes the body once and applies three guards (non-object body → absent key → empty/whitespace text), each raising a `ValueError` whose message names the client and the defect — matching the embedder's `"Ollama ..."` convention. Real text is returned unstripped, so the positive path is byte-identical to before. The tests use the injected `transport` seam with `httpx.MockTransport` and real `httpx.Response` objects (the superseding approach from spec 80), cover all four response-parsing cases plus the positive control, the transport failures, the conditional bearer header (including the `""` falsiness), the wire contract, and the timeout attribute. The embedder and the `LLMClient` ABC are untouched, as guarded.

## Findings

### 1. (Low) A present-but-non-string `response` value raises a bare `AttributeError`, not the typed `ValueError` — a gap in the embedder-parity the task requires

`src/llm/client.py:42-46`:

```python
if "response" not in body:
    raise ValueError("Ollama generate response is missing 'response'")

text = body["response"]
if not text.strip():
    raise ValueError("Ollama generate response text was empty")
```

The key-presence check and the `.strip()` check are separate, so a body where the key is present but its value is not a string — e.g. `{"response": null}` — passes the `"response" not in body` guard, then hits `None.strip()`. Verified at runtime:

```
{"response": null}  ->  AttributeError: 'NoneType' object has no attribute 'strip'
```

This is the exact anti-pattern the task set out to eliminate — "a missing key raises a bare `KeyError` from inside a client the caller has no reason to suspect" — reappearing for a slightly different malformed shape as a bare `AttributeError`. It also breaks the stated goal of giving the generator "the embedder's discipline": the embedder's `if not embeddings` guard *does* cleanly reject a null value (`{"embeddings": null}` → `ValueError`), because a single falsiness check covers both missing-key and null; the generator's split checks let null slip between them.

**Severity is low, not blocking:** spec 85 enumerates only three shapes (non-object body, absent key, empty/whitespace *text*), and a non-string value under a present key is outside that literal set. Ollama's `/api/generate` itself always returns a string (empty at worst, `""`), so the null case only arises from the same "proxy or broken tunnel" source the non-object guard already targets — the identical low-probability class, left half-covered. If the implementer wants full parity with the embedder's intent, folding the type into the empty check closes it, e.g. `if not isinstance(text, str) or not text.strip():` with a message covering both. Optional given the spec's enumerated scope; noted because the task's own framing ("no bare error from inside the client", "the embedder's discipline") is what it falls short of.

## Notes (no action needed)

- Guard order is safe: `isinstance(body, dict)` precedes any subscripting, so a `None`/string body cannot reach `body["response"]` and produce a `TypeError`.
- Validation was correctly moved just outside the `async with` block; `body` is already fully decoded into memory, so closing the client first is fine.
- `test_generate_raises_when_body_is_not_a_json_object` feeds `content=json.dumps(body)` for `None`/`"some string"`, which round-trips through `.json()` to a non-dict and exercises the first guard — a faithful reproduction of a non-object 200.
- The `api_key` omission test parametrizes both `None` and `""`, pinning the incidental falsiness so a later "tightening" to `is not None` (which would ship a bare `Bearer `) is caught.
- `httpx.URL == str` comparison in the wire-contract test is valid (httpx `URL.__eq__` accepts a `str`), and `json.loads(request.content)` asserts `stream: False`, guarding against a streaming NDJSON body.

REVIEW_PASS
