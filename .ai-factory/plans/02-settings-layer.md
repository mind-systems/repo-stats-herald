# Plan: Settings layer

## Context
Introduce a typed, env-backed configuration home in the cross-cutting `core/` module so Ollama connection and dev SSH-tunnel parameters have a single source of truth, injected downstream instead of read ad hoc.

## Settings
- Testing: no
- Logging: minimal
- Docs: no

## Tasks

### Phase 1: Configuration

- [x] **Task 1: Add `pydantic-settings` dependency**
  Files: `pyproject.toml`, `uv.lock`
  Run `uv add pydantic-settings` so the manifest and lockfile update atomically. `uv.lock` is committed and currently lacks `pydantic-settings` (only `pydantic`/`pydantic-core` are present, pulled transitively via fastapi), so a hand-edit of `pyproject.toml` alone would leave the lockfile drifting and produce an uncommitted `uv.lock` diff on the next `uv sync`/`uv run`. Commit both changed files. Keep the `dependencies` array formatting consistent.

- [x] **Task 2: Add `Settings` and `get_settings()`** (depends on Task 1)
  Files: `src/core/__init__.py`, `src/core/config.py`
  Create the `core` package (empty `__init__.py`) mirroring the existing `src/` module style. In `config.py` define `Settings(BaseSettings)` with `model_config = SettingsConfigDict(env_file=".env", extra="ignore")` and fields: `ollama_url: str = "http://localhost:11434"`, `ollama_model: str = "qwen2.5:14b-instruct-q4_K_M"`, `ollama_api_key: str | None = None`, `ssh_host: str | None = None`, `ssh_port: int = 22`, `ssh_key: str | None = None`. Add `@lru_cache`-decorated `get_settings() -> Settings` returning `Settings()`. No secrets or host IPs hardcoded — every value comes from env/`.env` (matches ARCHITECTURE.md: config read at composition root, injected into features).

- [x] **Task 3: Document env keys in `.env.example`** (depends on Task 2)
  Files: `.env.example`
  Create `.env.example` (the file does not exist yet — `.gitignore`'s `!.env.example` un-ignore rule anticipates it and ensures it will be tracked). Document every `Settings` key with uppercased names and non-secret default/placeholder values:
  ```
  OLLAMA_URL=http://localhost:11434
  OLLAMA_MODEL=qwen2.5:14b-instruct-q4_K_M
  OLLAMA_API_KEY=
  SSH_HOST=
  SSH_PORT=22
  SSH_KEY=
  ```
  `SSH_PORT` **must** carry its concrete default `22`, not an empty value: `ssh_port` is typed `int`, and pydantic v2 cannot coerce an empty string `""` to `int` — an empty `SSH_PORT=` raises `ValidationError`, which would break both the note's verify step (`Settings(_env_file=".env.example")`) and any developer who copies `.env.example` → `.env` verbatim. Empty placeholders are only safe for the `str | None` keys (`OLLAMA_API_KEY=`, `SSH_HOST=`, `SSH_KEY=` resolve to `""`). Real host/port/key stay in the developer's local `.env` (gitignored).
