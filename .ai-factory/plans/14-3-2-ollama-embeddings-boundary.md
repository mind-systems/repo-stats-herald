# Plan: 3.2 — Ollama embeddings boundary

## Context
Add a model-agnostic embeddings seam alongside the existing generation boundary, backed by Ollama, so the knowledge store (3.3) and indexer (3.4) can turn chunk text into fixed-dimension vectors.

## Settings
- Testing: no
- Logging: minimal
- Docs: no

## Tasks

### Phase 1: Config

- [x] **Task 1: Add `embed_model` to Settings**
  Files: `src/core/config.py`, `.env.example`
  In `Settings` add `embed_model: str = "nomic-embed-text"` (a local embedding model), placed next to the existing `ollama_*` fields. The embedder reuses the existing `ollama_url` / `ollama_api_key` — do not add a separate embed URL or key. In `.env.example`, add `EMBED_MODEL=nomic-embed-text` under the Ollama block (near `OLLAMA_MODEL`), documenting the key with no secret. The field name is fixed as `embed_model` by the spec/roadmap; `Settings` declares no `env_prefix` or aliases, so pydantic-settings binds it to the uppercased field name `EMBED_MODEL` (not `OLLAMA_EMBED_MODEL`). The `.env.example` key text **must** be `EMBED_MODEL` — an `OLLAMA_`-prefixed key would be silently ignored under `extra="ignore"`, leaving the field at its default. Follow the existing field/env-doc conventions in both files.

### Phase 2: Embedder boundary

- [x] **Task 2: Add `Embedder` ABC + `OllamaEmbedder`** (depends on Task 1)
  Files: `src/llm/embedder.py`
  New module mirroring the structure of `src/llm/client.py`.
  - `Embedder(ABC)` with one abstract async method `embed(self, texts: list[str]) -> list[list[float]]`. The abstraction names no Ollama concept (no model/url/httpx in its signature or docstring) — the backend must swap without touching callers.
  - `OllamaEmbedder(Embedder)` with a constructor matching `OllamaClient`'s shape: `(base_url: str, model: str, api_key: str | None = None, timeout: float = 120.0)`, stored on private attributes. Bearer `Authorization` header added only when `api_key` is set (same pattern as `OllamaClient.generate`).
  - `embed` POSTs to `{base_url}/api/embed` with `{"model": self._model, "input": texts}` (Ollama's native batch endpoint; returns `embeddings` as a list aligned to `input`). Use a single `httpx.AsyncClient(timeout=self._timeout)` request for the whole batch. Call `response.raise_for_status()` so timeouts/transport/HTTP errors propagate.
  - Guards: after parsing, validate the response — extract `embeddings`; raise a `ValueError` (never return `[]`) if the key is missing, the list is empty, its length does not match `len(texts)`, or any inner vector is empty. This is the "failed/empty response raises" guard.
  - Stable dimension: assert all returned vectors share the same length; raise `ValueError` on any mismatch. Return `list[list[float]]` in input order.
  - Handle the trivial `texts == []` input by returning `[]` before making a request (no call for nothing to embed).
