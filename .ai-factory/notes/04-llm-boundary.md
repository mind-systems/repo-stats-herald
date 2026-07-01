# llm/ Boundary — Model-Agnostic LLM Client

**Date:** 2026-07-01
**Source:** conversation context

## Key Findings

- There is no seam to the LLM. Calling Ollama directly from the summarizer would hardwire a 14B local model into the business logic and make the eventual upgrade (bigger/hosted model) a rewrite.
- This task adds the `llm/` infrastructure module: an abstract `LLMClient` and a concrete `OllamaClient`. `LLMClient` names no Ollama concept — it is the single swap point the whole project depends on.

## Details

### Current state
No LLM access. Settings (task 02) already exposes `ollama_url` / `ollama_model` / `ollama_api_key`.

### Target
- `src/llm/__init__.py`
- `src/llm/client.py`:
  ```python
  from abc import ABC, abstractmethod

  class LLMClient(ABC):
      @abstractmethod
      async def generate(self, prompt: str) -> str: ...

  class OllamaClient(LLMClient):
      def __init__(self, base_url: str, model: str, api_key: str | None = None,
                   timeout: float = 120.0) -> None: ...
      async def generate(self, prompt: str) -> str:
          # POST {base_url}/api/generate  {"model": ..., "prompt": ..., "stream": false}
          # Authorization: Bearer <api_key>  (only if provided)
          # returns response["response"]
  ```
  Uses `httpx.AsyncClient`. Add dependency `httpx` to `pyproject.toml`.

### Architecture notes
`llm/` is a feature-independent infra module (the analogue of mind's global `mail/`) — summarization depends on the abstract `LLMClient`, and the composition root (task 06) injects a concrete `OllamaClient` built from `Settings`. `OllamaClient` takes primitives in its constructor, not a `Settings` object, so it stays trivially unit-testable and unaware of the config layer.

### Guards
- `LLMClient.generate` must expose no Ollama-specific type in its signature — the abstraction is the whole point.
- Timeouts and HTTP/connection errors surface as raised exceptions, never a silent empty string. A 14B model on a tunneled connection is slow — default timeout generous (~120s).
- Do not stream for the spike (`stream: false`) — keep it a single request/response.

### Verify
- With the SSH tunnel up (task 06) and `.env` pointing `OLLAMA_URL=http://localhost:11434`:
  `await OllamaClient(base_url, model).generate("Say hi in one word")` returns a non-empty string from the real server.

## Open Questions

- Server-side auth shape is unconfirmed. With the tunnel as the auth boundary, `api_key` likely stays unused; the header is added only when `api_key` is set, so both cases work without code change.
