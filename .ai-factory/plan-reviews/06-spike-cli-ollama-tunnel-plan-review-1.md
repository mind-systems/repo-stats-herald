# Plan Review: 06 — Spike CLI + Ollama tunnel

**Plan:** `.ai-factory/plans/06-spike-cli-ollama-tunnel.md`
**Files Reviewed:** 3 tasks (spike script + 2 Makefile targets) against `src/`, `Makefile`, `.env.example`, `pyproject.toml`
**Risk Level:** 🟡 Medium — API wiring is correct, but the stated run command fails at import time (verified empirically). One-line fix.

## Context Gates

- **Architecture (`.ai-factory/ARCHITECTURE.md`):** ✅ PASS. The plan honors the composition-root pattern (`scripts/*` as the wiring point), constructor DI, no env reads inside features, and no hardcoded secrets. Task 1's "assembly only" guard directly mirrors the "Logic in entry points" anti-pattern. No boundary violations.
- **Rules (`.ai-factory/RULES.md`):** ⚠️ WARN — file not present (optional). No explicit convention set to enforce.
- **Roadmap (`.ai-factory/ROADMAP.md`):** ✅ PASS. Maps 1:1 to the active Phase 1 task "Spike CLI + Ollama tunnel" (script + idempotent `tunnel` + `dev`, params from `.env`). Linkage is explicit; spec note `06-spike-cli-tunnel.md` exists and agrees.

## Verified — Correct Assumptions

All API/import assumptions in Tasks 1 hold against the real code:

- `get_settings()` ← `src/core/config.py` ✓
- `GitCommitCollector().collect(repo_path, rev_range)` ← `src/commits/collector.py` ✓ (positional args match)
- `OllamaClient(settings.ollama_url, settings.ollama_model, settings.ollama_api_key)` — constructor is `(base_url, model, api_key=None, timeout=120.0)`; positional mapping is exact ✓
- `Summarizer(llm, prompt).summarize(ctx, lang)` is `async` → `asyncio.run(...)` is correct ✓
- `PromptBuilder()` ← `src/summarization/prompt.py` ✓
- `.env.example` already carries `SSH_HOST/SSH_PORT/SSH_KEY` and `OLLAMA_URL` — no new keys required.

## Critical Issues

### 1. The stated invocation `uv run python scripts/summarize_range.py` fails with `ModuleNotFoundError: No module named 'src'`

This is a **blocking** runtime bug, not a style nit. When you run `python scripts/summarize_range.py`, Python puts the **script's own directory** (`scripts/`) on `sys.path[0]`, not the project root. The project defines **no `[build-system]`** in `pyproject.toml`, so `uv sync` does not install `src` as a package — `src.*` is importable only when the project root is on the path. Result: the very first line `from src.core.config import get_settings` raises `ModuleNotFoundError`.

Verified empirically in this repo:

```
$ uv run python scripts/_probe.py
sys.path[0]= /Users/max/projects/repo-stats-herald/scripts
IMPORT_FAIL ModuleNotFoundError No module named 'src'
```

(This is why `make run` works but this won't: `uvicorn src.main:app` inserts CWD onto the path; a bare `python scripts/x.py` does not.)

This affects **three places** that must be corrected together:
- Task 1's stated command (`uv run python scripts/summarize_range.py`)
- Task 3's `dev` target (same command)
- the spec note's Verify section (same command)

**Fix (pick one, verified working in this repo):**
- **Preferred — run as a module:** `uv run python -m scripts.summarize_range --repo . --range HEAD~3..HEAD`. Confirmed `IMPORT_OK` even without a `scripts/__init__.py`. Keeps the script clean (no path hacks). Update Task 1, Task 3, and the note to this form.
- **Or set the path in the Makefile recipe:** `PYTHONPATH=. uv run python scripts/summarize_range.py ...`. Also confirmed `IMPORT_OK`.
- **Or bootstrap inside the script** (`sys.path.insert(0, str(Path(__file__).resolve().parent.parent))` before the `src` imports) — works but adds non-wiring code to the composition root, so less clean.

The plan should name the chosen approach explicitly so the implementer doesn't reproduce the failing command.

## Medium Issues

### 2. `include .env` will break the existing `install`/`run` targets when `.env` is absent

Task 2 suggests `include .env` to load `SSH_*`. A hard `include` is evaluated globally, and if `.env` does not exist (fresh clone, CI, before the dev fills it in), `make` aborts with `.env: No such file or directory` for **every** target — including the `install`/`run` targets Task 3 requires to stay intact. Use the optional form:

```makefile
-include .env   # leading dash: missing file is not an error
export
```

This confines `.env` dependence to the `tunnel`/`dev` path.

## Minor / Advisory

- **SSH user is unmodeled.** The command `ssh ... $(SSH_HOST)` has no user component, and neither `.env.example` nor `Settings` defines `SSH_USER`. The note's Open Questions lists "user" as needed. State the convention explicitly — dev sets `SSH_HOST=user@1.2.3.4` (or relies on `~/.ssh/config`) — so the implementer doesn't add a phantom `SSH_USER` var or produce a command that connects as the local username.
- **Idempotency probe portability / exit codes.** `nc -z localhost 11434` is fine on macOS; ensure the Make recipe branches on its exit status correctly (e.g. `nc -z localhost 11434 || ssh ...` on one line, since each recipe line is a separate shell). The note's `lsof -i :11434` is an acceptable fallback. Advisory only.
- **Startup race (low risk).** `dev` runs the script immediately after `ssh -f -N`. With `-f`, ssh backgrounds only after the local forward is established, so the port is normally ready; flagged only as a low-likelihood first-run flake.
- **`--range` dest.** `argparse` maps `--range` to `args.range`; attribute access does not shadow the `range` builtin, so this is safe as written.

## Positive Notes

- Correct instinct to keep the tunnel a **dev-only Makefile concern** and out of application code — matches the architecture note precisely.
- Strong anti-pattern guardrails restated per task (assembly-only root; secrets only from `.env`; idempotent tunnel).
- `argparse` over `typer` is the right call — no new dependency for a spike.
- Dependency ordering (Task 1 → 2 → 3) and the double-`make dev` idempotency verify are well specified.

## Verdict

One blocking issue (#1) makes the milestone's own verify path (`make dev` → summary) fail as written; #2 risks regressing existing targets. Both are small, well-understood fixes. Address these before implementation.
