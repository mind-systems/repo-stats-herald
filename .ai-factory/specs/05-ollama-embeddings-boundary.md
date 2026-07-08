# 3.2 — Ollama embeddings boundary

**Phase:** 3 — Repo mirror & semantic memory. Independent of 3.1; the store (3.3) and indexer (3.4) consume it.

## Current state

`src/llm/client.py` has `LLMClient` (ABC) + `OllamaClient` for **text generation** only (`generate(prompt) -> str`). The knowledge store needs **vector embeddings** of chunk text, which the generation client does not produce. `Settings` has `ollama_url`/`ollama_model` but no embedding model.

## Change

Add a model-agnostic embeddings boundary alongside the generation boundary, backed by Ollama.

- Extend `src/core/config.py` `Settings` with `embed_model: str` (default a local embedding model, e.g. `nomic-embed-text`).
- `src/llm/embedder.py`:
  - `Embedder` (ABC) — `embed(texts: list[str]) -> list[list[float]]`; names no Ollama concept.
  - `OllamaEmbedder(Embedder)` — `httpx` → `{ollama_url}/api/embeddings` (or `/api/embed` batch), takes `base_url`, `model`, optional `api_key`, `timeout`; bearer only if key set. Batches the input texts.
- Wired at the composition root (same pattern as `OllamaClient`).

## Files & types

- edit `src/core/config.py` (`embed_model`)
- new `src/llm/embedder.py` (`Embedder`, `OllamaEmbedder`)

## Guards

- `Embedder` abstraction names no Ollama concept — the backend swaps without touching callers.
- Timeouts/transport errors raise; an empty or malformed embedding response raises rather than returning `[]`.
- Output vectors have a stable dimension for the configured model (the store's column dimension must match — see 3.3).
- Reached over the SSH tunnel in dev (`make tunnel`), like generation.

## Verification

- Through the tunnel, `embed(["hello", "world"])` returns two vectors of the model's fixed dimension.
- A transport failure raises, never returns empty.
