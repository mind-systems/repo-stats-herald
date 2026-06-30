# Base Rules

> Auto-detected conventions. Edit as needed.

## Naming Conventions

- Files: `snake_case.py`
- Variables: `snake_case`
- Functions: `snake_case`
- Classes: `PascalCase`

## Module Structure

- `src/` — application source
- `src/routes/` — FastAPI route handlers
- `src/services/` — business logic (ollama, github, telegram, changelog)
- `src/models/` — Pydantic models
- `src/config.py` — settings via env vars

## Error Handling

- Raise HTTP exceptions at route level
- Services raise plain Python exceptions, routes catch and convert
- Log all errors with context before re-raising

## Logging

- Use Python `logging` module with structured output
- Log level configurable via `LOG_LEVEL` env var
