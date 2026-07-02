# Plan: Project scaffold

## Context
Deliver the smallest bootable unit: a uv-managed FastAPI application with a single `GET /health` route, proving the toolchain installs, boots, and serves. Skeleton only — no business logic.

## Settings
- Testing: no
- Logging: minimal
- Docs: no

## Tasks

### Phase 1: uv application setup

- [x] **Task 1: Create the uv application manifest**
  Files: `pyproject.toml`
  Define a runnable uv application (NOT a distributed package — do **not** add a `[build-system]` section). Fields: `[project]` with `name = "repo-stats-herald"`, `version = "0.1.0"`, `requires-python = ">=3.12"`, and `dependencies = ["fastapi", "uvicorn[standard]"]`. `uv sync` / `uv run` manage `.venv` and the lock. No other config.

### Phase 2: Application skeleton

- [x] **Task 2: Create the package marker** (depends on Task 1)
  Files: `src/__init__.py`
  Empty file marking `src` as the importable package, so later imports resolve as `from src.<feature>...`. Per `.ai-factory/ARCHITECTURE.md`, `src/` is the application root organized by feature.

- [x] **Task 3: Create the composition root with the health route** (depends on Task 2)
  Files: `src/main.py`
  Create the FastAPI app and the single health endpoint. This is the composition root per `.ai-factory/ARCHITECTURE.md` — the only place concrete wiring will later happen. Health is a standalone route on the app, not a feature module. Implement exactly:
  ```python
  from fastapi import FastAPI

  app = FastAPI(title="repo-stats-herald")

  @app.get("/health")
  async def health() -> dict[str, str]:
      return {"status": "ok"}
  ```
  No config, no logging, no external clients — strictly the skeleton.

### Phase 3: Dev ergonomics

- [x] **Task 4: Add a minimal Makefile** (depends on Task 3)
  Files: `Makefile`
  Two targets only:
  - `install:` → `uv sync`
  - `run:` → `uv run uvicorn src.main:app --reload --port 8000`
  Declare both as `.PHONY`. Do not add `dev`/`tunnel` targets — those arrive in a later milestone.

## Verification
- `make install` succeeds (creates `.venv`, resolves fastapi + uvicorn).
- `make run` boots uvicorn without error.
- `curl -s localhost:8000/health` → HTTP 200, body `{"status":"ok"}`.
