# Settings Layer — pydantic-settings

**Date:** 2026-07-01
**Source:** conversation context

## Key Findings

- There is nowhere to hold the Ollama connection (URL, model, optional key) or the dev-only SSH tunnel parameters. Every later task that touches an external system needs a typed, env-backed config first.
- This task adds a single `Settings` class (pydantic-settings) in the cross-cutting `core/` module plus a documented `.env.example`. Secrets never live in code.

## Details

### Current state
No configuration mechanism. Only `.env` / `.env.*` are gitignored (already in `.gitignore`, with `!.env.example` un-ignored).

### Target
- `src/core/__init__.py`, `src/core/config.py`:
  ```python
  from functools import lru_cache
  from pydantic_settings import BaseSettings, SettingsConfigDict

  class Settings(BaseSettings):
      model_config = SettingsConfigDict(env_file=".env", extra="ignore")

      # LLM boundary
      ollama_url: str = "http://localhost:11434"
      ollama_model: str = "qwen2.5:14b-instruct-q4_K_M"
      ollama_api_key: str | None = None

      # Dev-only SSH tunnel to reach Ollama on the server (see task 06)
      ssh_host: str | None = None
      ssh_port: int = 22
      ssh_key: str | None = None

  @lru_cache
  def get_settings() -> Settings:
      return Settings()
  ```
- `.env.example` — documents every key with empty/placeholder values, no real secrets:
  ```
  OLLAMA_URL=http://localhost:11434
  OLLAMA_MODEL=qwen2.5:14b-instruct-q4_K_M
  OLLAMA_API_KEY=
  SSH_HOST=
  SSH_PORT=
  SSH_KEY=
  ```
- Add dependency `pydantic-settings` to `pyproject.toml`.

### Architecture notes
`core/` is the cross-cutting module (mirrors mind_mobile's `Core/`). `Settings` is consumed via `get_settings()` and injected into constructors downstream — features never read env directly. This keeps the config a single source of truth and the classes testable (pass a `Settings` in).

### Guards
- Secrets come only from env / `.env`; never hardcode a key, URL, or host IP in committed code.
- The real host, port, and key path live in the developer's local `.env`, never in `.env.example` or source.

### Verify
- Construct `Settings(_env_file=".env.example")` (or with a temp env) → fields populate with the documented defaults.
- App from task 01 still boots.

## Open Questions

- Whether `ollama_api_key` is actually needed depends on server auth; with the SSH-tunnel approach (task 06) the tunnel is the auth boundary and the key may stay `None`.
