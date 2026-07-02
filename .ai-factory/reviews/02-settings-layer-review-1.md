# Code Review: 02 — Settings layer

## Summary

**Files reviewed (in full):** `src/core/config.py`, `src/core/__init__.py`, `.env.example`, `pyproject.toml`, `uv.lock`, plus `src/main.py` for context.
**Risk level:** 🟢 Low — pure config plumbing, no branching logic, no downstream consumers yet.

The implementation matches the plan and spec exactly. All three round-1 plan-review findings are correctly reflected in the code (`SSH_PORT=22`, `.env.example` created, `uv.lock` updated atomically with `pydantic-settings` + its new transitive deps `python-dotenv`/`typing-inspection`).

## Runtime verification (executed)

Ran against the project environment:

- `Settings(_env_file='.env.example')` → loads cleanly, no `ValidationError`; `ssh_port` coerces to `22`. Confirms the round-1 critical fix holds in practice.
- `get_settings()` returns defaults with `ollama_api_key = None`; `@lru_cache` returns the same instance across calls (single-source-of-truth verified).
- `import src.main` → FastAPI app still boots (`title == "repo-stats-herald"`). No import-time regression from the new package.

## Findings

### 1. Observation (non-blocking, forward-looking): empty `.env` placeholders resolve to `""`, not `None`

When settings are loaded from a file containing the `.env.example` lines `OLLAMA_API_KEY=`, `SSH_HOST=`, `SSH_KEY=`, those three fields populate as empty strings `""` rather than `None`. Verified: `Settings(_env_file='.env.example').model_dump()` yields `{'ollama_api_key': '', 'ssh_host': '', 'ssh_key': ''}`, whereas plain `Settings()` (no file) yields `None` for all three.

This is **not a bug in this diff** — there are no consumers yet, and both `""` and `None` are falsy, so idiomatic `if settings.ssh_host:` guards behave identically. The trap is latent for a downstream task (e.g. the task-06 SSH tunnel): any consumer that distinguishes with `is None` / `is not None` — for example "tunnel enabled only when `ssh_host is not None`" — will misread a copied-and-blanked `.env` as *configured with an empty host* instead of *unset*.

No change required now. Flagging so whoever wires these fields uses truthiness checks (`if settings.ssh_host:`), not `is None`, or normalizes empty strings to `None` at that seam.

## Positive notes

- `pydantic_settings.BaseSettings` + `SettingsConfigDict(env_file=".env", extra="ignore")` is the correct v2 API; case-insensitive env mapping means the uppercased `.env.example` keys resolve to the lowercase fields.
- Secret hygiene is clean: only non-secret defaults in code, no host IP / key committed, real values stay in the gitignored `.env` — matches ARCHITECTURE.md's anti-pattern list.
- `uv.lock` is internally consistent — `pydantic-settings 2.14.2` appears both as a package entry and under the project's `dependencies` + `requires-dist`, with `python-dotenv` (needed for `env_file` support) present.
- Files land exactly where ARCHITECTURE.md prescribes (`src/core/`).

## Note↔code consistency

The spec note `notes/02-settings-layer.md` still shows the pre-fix `SSH_PORT=` (empty) block; the code correctly uses `SSH_PORT=22`. This was already flagged in plan-review round 2 as a non-blocking note-drift nit and does not affect the shipped code.

The single finding above is a non-blocking forward-looking observation, not a defect in the current changes.

REVIEW_PASS
