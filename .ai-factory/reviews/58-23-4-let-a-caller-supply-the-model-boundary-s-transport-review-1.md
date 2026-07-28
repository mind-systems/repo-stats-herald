# Review: 23.4 — Let a caller supply the model boundary's transport

## Scope
Code changes to `src/llm/client.py` and `src/llm/embedder.py`.

## What was checked
- The diff matches the plan and spec exactly: a keyword parameter `transport: httpx.AsyncBaseTransport | None = None` added as the last argument of both `OllamaClient.__init__` and `OllamaEmbedder.__init__`, stored as `self._transport`, and threaded into `httpx.AsyncClient(timeout=self._timeout, transport=self._transport)`.
- **Production wiring unchanged (key guard):** verified that `httpx.AsyncClient.__init__`'s own default for `transport` is `None`, and the client builds its default transport internally when it receives `None`. Therefore `transport=self._transport` with the `None` default is behaviorally identical to the previous `httpx.AsyncClient(timeout=self._timeout)`. The composition root and script entrypoints, which never pass `transport`, reach the real backend exactly as before.
- **Type annotation:** `httpx.AsyncBaseTransport` is the correct base type for both sync/async transports supplied to an async client (e.g. `httpx.MockTransport`, `httpx.ASGITransport`), matching httpx's own signature.
- **Boundary-agnostic guard:** the abstract `LLMClient` and `Embedder` are untouched — they gain no transport concept and stay swappable.
- **No behaviour-change slipped in:** `generate` still returns `response.json()["response"]` with no added validation; the embedder's response-validation checks are unchanged. The generator's known validation asymmetry correctly stays out of scope.
- **Out-of-scope guard respected:** the three delivery clients were not touched.

## Findings
None. The change is minimal, correct, and satisfies every guard in the spec.

REVIEW_PASS
