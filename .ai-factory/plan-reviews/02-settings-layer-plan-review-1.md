# Plan Review: 02 — Settings layer

## Code Review Summary

**Files Reviewed:** plan `02-settings-layer.md` (+ note `02-settings-layer.md`), against `pyproject.toml`, `uv.lock`, `Makefile`, `.gitignore`, `src/`, ARCHITECTURE.md, ROADMAP.md, rules/base.md
**Risk Level:** 🟡 Medium

The plan is well-scoped and architecturally aligned: paths (`src/core/config.py`, `src/core/__init__.py`) match ARCHITECTURE.md, config-at-root-injected-downstream is respected, no secrets are hardcoded, and it maps cleanly to the ROADMAP "Settings layer" task. One concrete correctness bug and a few missing/assumption issues keep it from passing as-is.

### Context Gates
- **Architecture (ARCHITECTURE.md):** ✅ PASS. `core/` as the cross-cutting config home, `Settings` read via `get_settings()` and injected, primitives passed to concrete clients — all consistent with the documented feature-modular + DI design.
- **Rules (rules/base.md):** ⚠️ WARN. `base.md` still describes a layer-first layout (`src/config.py`, `src/services/`, `src/models/`) that directly contradicts ARCHITECTURE.md's feature-modular design. The plan correctly follows ARCHITECTURE.md (`src/core/config.py`), which is the authoritative doc (base.md is self-labeled "Auto-detected conventions. Edit as needed."). Non-blocking, but `base.md` should be updated to avoid misleading future tasks.
- **Roadmap (ROADMAP.md):** ✅ PASS. Task corresponds to the unchecked "Settings layer" line; fields and guards match the roadmap contract line.

### Critical Issues

**1. `.env.example` `SSH_PORT=` (empty) will raise a ValidationError.**
Task 3 documents `SSH_PORT=` with an empty value, but `Settings` defines `ssh_port: int = 22`. An empty env value is the string `""`, and pydantic v2 cannot coerce `""` to `int` — it raises `ValidationError` (verified locally against the installed pydantic 2.13.x). This bites in two real paths:
- The note's own **Verify** step — `Settings(_env_file=".env.example")` — loads `SSH_PORT=""` and fails, so the plan's acceptance check cannot pass as written.
- Any developer who copies `.env.example` → `.env` verbatim crashes the app at settings construction.

Fix one of: emit `SSH_PORT=22` (mirror the default), comment the line out (`# SSH_PORT=22`), or omit `SSH_PORT` from `.env.example` entirely. The same care applies to any future non-string/optional int keys — empty placeholders are only safe for `str`/`str | None` fields (`OLLAMA_API_KEY=`, `SSH_HOST=`, `SSH_KEY=` are fine; they resolve to `""`/valid strings).

### Issues / Missing Steps

**2. Wrong assumption: `.env.example` does not exist yet.**
Task 3 says "Fill the currently-empty `.env.example`", but there is no `.env.example` in the repo (only `.gitignore`'s `!.env.example` un-ignore rule anticipates one). The task must **create** the file, not fill an existing one. The resulting action is the same (write the file), and `!.env.example` already ensures it will be tracked — but the false premise should be corrected so the implementer doesn't go looking for a file that isn't there.

**3. Missing step: `uv.lock` will drift from `pyproject.toml`.**
`uv.lock` is committed and `pydantic-settings` is **not** currently in it (only `pydantic`/`pydantic-core`, pulled transitively via fastapi). Task 1 edits `pyproject.toml` by hand and says nothing about the lockfile. Prefer `uv add pydantic-settings` (updates manifest + lock atomically), or explicitly run `uv lock` / `uv sync` and commit the updated `uv.lock`. Otherwise `make install` (`uv sync`) / `make run` (`uv run`) will re-resolve and leave an uncommitted lockfile diff, and the "app still boots" verify becomes ambiguous.

### Positive Notes
- Field set, types, defaults, and `SettingsConfigDict(env_file=".env", extra="ignore")` are sensible and match the spec note exactly.
- `@lru_cache`-decorated `get_settings()` is the correct single-source-of-truth pattern and keeps downstream classes testable (inject a `Settings`).
- Strong secret hygiene: defaults are non-secret, real host/port/key are kept in local `.env` (gitignored), nothing sensitive lands in committed code — matches ARCHITECTURE.md's anti-pattern list.
- Dependency ordering (Task 2 → Task 1, Task 3 → Task 2) is correct.
- `pydantic` is already available transitively, so `pydantic-settings` is the only genuinely new top-level requirement.

### Recommendation
Address Critical #1 (and ideally #2/#3) before implementation. Small, mechanical fixes — but #1 breaks the plan's own verification step.
