# Project Scaffold — Runnable FastAPI + uv

**Date:** 2026-07-01
**Source:** conversation context

## Key Findings

- The repo has no runnable Python application yet — only `.ai-factory/`, `CLAUDE.md`, `.mcp.json`, `.gitignore`. Nothing proves the toolchain installs, builds, and boots.
- This task delivers the minimal bootable skeleton: a uv project and a FastAPI app with a single `GET /health` route. It is the first closed task and the proof that the stack works end to end.
- Skeleton only — no business logic, no external calls, no config. Those arrive in later tasks.

## Details

### Current state
Empty of code. No `pyproject.toml`, no `src/`, no entrypoint.

### Target
- `pyproject.toml` — uv-managed **application** (not a distributed library, so no `[build-system]`). Fields: `name = "repo-stats-herald"`, `requires-python = ">=3.12"`, `dependencies = ["fastapi", "uvicorn[standard]"]`. `uv sync` / `uv run` create and manage `.venv`.
- `src/__init__.py` — marks `src` as the importable package (imports look like `from src.core.config import Settings` later).
- `src/main.py` — the composition root and app bootstrap:
  ```python
  from fastapi import FastAPI

  app = FastAPI(title="repo-stats-herald")

  @app.get("/health")
  async def health() -> dict[str, str]:
      return {"status": "ok"}
  ```
- `Makefile` — minimal dev ergonomics:
  - `install:` → `uv sync`
  - `run:` → `uv run uvicorn src.main:app --reload --port 8000`
  (The `tunnel` / `dev` targets are added later in task 06 when Ollama is first hit.)

### Architecture notes
Feature-modular layout is established from the first commit even though only `main.py` exists now — see `.ai-factory/ARCHITECTURE.md`. `src/main.py` is the composition root: it is the only place allowed to wire concrete implementations together. Health is a standalone route on the app (mirrors mind_api's standalone `health.controller.ts`), not a feature module.

### Guards
- No config, no LLM, no git, no network — strictly the skeleton.
- Do not add a `[build-system]` / packaging config — this is a runnable app, not a published package.

### Verify
- `make install` succeeds (creates `.venv`, resolves fastapi + uvicorn).
- `make run` boots without error.
- `curl -s localhost:8000/health` → `200` with body `{"status":"ok"}`.

## Open Questions

None — this is deliberately the smallest possible bootable unit.
