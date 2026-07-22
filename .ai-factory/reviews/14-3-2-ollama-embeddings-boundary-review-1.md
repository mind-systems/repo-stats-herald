# Code Review: 3.2 — Ollama embeddings boundary

**Files reviewed (code):** `src/core/config.py`, `.env.example`, `src/llm/embedder.py` (new)
**Risk Level:** 🟢 Low

Reviewed the full changed files (not just the diff) against the plan `14-3-2-ollama-embeddings-boundary.md`, the spec `.ai-factory/specs/05-ollama-embeddings-boundary.md`, and the sibling `src/llm/client.py`. Both changed Python files compile (`py_compile` clean).

## Correctness

- **`embed_model` config (`config.py`):** Field added as `embed_model: str = "nomic-embed-text"` next to the `ollama_*` fields, and `.env.example` documents the key as `EMBED_MODEL` — the uppercased field name pydantic-settings actually binds (no `env_prefix`/alias on `Settings`). The plan-review-1 hazard (an `OLLAMA_`-prefixed key silently discarded under `extra="ignore"`) is not present. Correct.
- **Boundary discipline (`embedder.py`):** `Embedder(ABC).embed(texts) -> list[list[float]]` names no Ollama concept; `OllamaEmbedder` mirrors `OllamaClient` exactly — same constructor `(base_url, model, api_key=None, timeout=120.0)`, bearer header only when `api_key` is set, `raise_for_status()` so timeouts/transport/HTTP errors propagate rather than yielding a silent empty result. Matches the architecture's LLM-seam rules.
- **Endpoint/payload:** `POST {base_url}/api/embed` with `{"model", "input": texts}` → `embeddings` is Ollama's native batch shape (aligned `embeddings` list out); the only form that expresses the `list[str] -> list[list[float]]` contract. Spec-conformant.
- **Failure guards match the spec's "empty/malformed raises, never `[]`":**
  - `not embeddings` catches both a missing key (`None`) and an empty list → `ValueError`.
  - length ≠ `len(texts)` → `ValueError`.
  - `any(not vector ...)` catches empty inner vectors → `ValueError`.
  - `len(dimensions) > 1` catches cross-vector dimension mismatch → `ValueError` (stable-dimension guard).
  - The `texts == []` short-circuit returns `[]` before any request and before the dimension asserts, so those checks never run on an empty batch. Ordering is sound.

## Security

- No secrets logged or committed; the bearer token comes only from the injected `api_key` primitive, and `.env.example` carries no value. No injection surface — `texts` travel as a JSON body field, not interpolated into the URL. Clean.

## Runtime concerns

- No migration, type-mismatch, or concurrency surface here: a stateless client that opens and closes its own `httpx.AsyncClient` per call. No composition-root wiring is added, which is correct — the first consumer is the 3.4 indexer, so wiring now would be dead code (consistent with the plan and both plan-reviews).
- Minor, non-blocking: if a backend ever returned a JSON body that is not an object, `body.get(...)` would raise `AttributeError` rather than `ValueError`. Ollama's `/api/embed` always returns a JSON object on 2xx, so this is not reachable in practice — noting only for completeness, not as a finding.

No correctness, security, or runtime defects found.

REVIEW_PASS
