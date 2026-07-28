# Plan: 23.4 — Let a caller supply the model boundary's transport

## Context
Add an optional `transport` parameter to the two concrete LLM-boundary implementations (`OllamaClient`, `OllamaEmbedder`) and pass it through to the `httpx.AsyncClient` they build inside their call, so a caller can drive the boundary with a supplied stub transport instead of replacing the module's client symbol.

## Settings
- Testing: no
- Logging: minimal
- Docs: no

## Tasks

### Phase 1: Open the transport seam on both concretes

- [x] **Task 1: Accept and thread `transport` through `OllamaClient`**
  Files: `src/llm/client.py`
  Add a keyword parameter `transport: httpx.AsyncBaseTransport | None = None` as the last argument of `OllamaClient.__init__`, after `timeout`. Store it as `self._transport = transport`. In `generate`, pass it to the client construction: `httpx.AsyncClient(timeout=self._timeout, transport=self._transport)`. Leave the abstract `LLMClient` untouched — it gains no transport concept. Do not touch the response handling (`response.raise_for_status()` / `response.json()["response"]`); the generator's missing-response-validation asymmetry is a separate task and stays out.

- [x] **Task 2: Accept and thread `transport` through `OllamaEmbedder`**
  Files: `src/llm/embedder.py`
  Mirror Task 1 exactly: add `transport: httpx.AsyncBaseTransport | None = None` as the last keyword argument of `OllamaEmbedder.__init__` after `timeout`, store `self._transport`, and pass `transport=self._transport` into `httpx.AsyncClient(timeout=self._timeout, transport=self._transport)` inside `embed`. Leave the abstract `Embedder` and all existing response-validation checks (missing/empty embeddings, count mismatch, empty vector, mismatched dimensions) unchanged.
