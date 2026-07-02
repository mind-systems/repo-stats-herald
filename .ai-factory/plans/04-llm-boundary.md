# Plan: llm/ boundary

## Context
Introduce a model-agnostic LLM seam (`src/llm/`) so business logic depends on an abstract `LLMClient` while `OllamaClient` is the swappable concrete backend — keeping the 14B Ollama model out of feature code.

## Settings
- Testing: no
- Logging: minimal
- Docs: no

## Tasks

### Phase 1: LLM boundary module

- [x] **Task 1: Add httpx dependency**
  Files: `pyproject.toml`
  Add `httpx` to the `dependencies` list in `pyproject.toml` (alongside `fastapi`, `pydantic-settings`, `uvicorn[standard]`). This is required by `OllamaClient` for async HTTP calls to Ollama. Run `uv lock`/`uv sync` if a lockfile is present so the dependency is resolved.

- [x] **Task 2: Create llm package init** (depends on Task 1)
  Files: `src/llm/__init__.py`
  Add an empty `__init__.py` to make `src/llm/` an importable package, matching the existing `src/core/__init__.py` and `src/commits/__init__.py` convention.

- [x] **Task 3: Implement LLMClient ABC and OllamaClient** (depends on Task 2)
  Files: `src/llm/client.py`
  Implement the model-agnostic boundary:
  - `LLMClient(ABC)` with a single `@abstractmethod async def generate(self, prompt: str) -> str`. The signature must name **no** Ollama-specific concept (no model, no url) — this abstraction is the whole point of the module.
  - `OllamaClient(LLMClient)` with `__init__(self, base_url: str, model: str, api_key: str | None = None, timeout: float = 120.0)`. It takes primitives only — never a `Settings` object (per ARCHITECTURE.md dependency rules; the composition root injects it later).
  - `generate` POSTs to `{base_url}/api/generate` with JSON body `{"model": self._model, "prompt": prompt, "stream": false}` using `httpx.AsyncClient` and the configured `timeout`. Add an `Authorization: Bearer <api_key>` header **only** when `api_key` is set. Call `response.raise_for_status()` and return `response.json()["response"]`.
  - Guards: timeouts and HTTP/connection errors must surface as raised exceptions — never a silent empty string. Do not stream (`stream: false`), keep it a single request/response. Do not read env or construct `Settings` inside the client.
  - Keep all HTTP/Ollama specifics encapsulated inside `OllamaClient`; expose nothing Ollama-shaped through `LLMClient`.
