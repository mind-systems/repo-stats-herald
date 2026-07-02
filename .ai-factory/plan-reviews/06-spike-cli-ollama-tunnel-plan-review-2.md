# Plan Review 2: 06 — Spike CLI + Ollama tunnel

**Plan:** `.ai-factory/plans/06-spike-cli-ollama-tunnel.md`
**Files Reviewed:** 3 tasks (spike script + 2 Makefile targets) against `src/`, `Makefile`, `.env.example`, `pyproject.toml`, `ARCHITECTURE.md`, `ROADMAP.md`, spec note `06-spike-cli-tunnel.md`
**Risk Level:** 🟢 Low — every blocking and medium issue from review 1 is now resolved; all API/import assumptions re-verified empirically in this repo.

## Context Gates

- **Architecture (`.ai-factory/ARCHITECTURE.md`):** ✅ PASS. The plan is an exact instance of the documented composition-root pattern: `scripts/summarize_range.py` is named in ARCHITECTURE's Folder Structure and Dependency Rules as the spike wiring point, and the "assembly only, no business logic" guard maps 1:1 to the "Logic in entry points" anti-pattern. The DI wiring in Task 1 (`Summarizer(OllamaClient(...), PromptBuilder())`) is character-for-character the example in ARCHITECTURE's "Layer / Feature Communication" section. Keeping the tunnel a Makefile-only, dev-only concern honors "Hardcoded secrets or host details" and "Config is injected" principles.
- **Rules (`.ai-factory/RULES.md`):** ⚠️ WARN — file not present (optional). No explicit convention set to enforce.
- **Roadmap (`.ai-factory/ROADMAP.md`):** ✅ PASS. Maps 1:1 to the active Phase 1 task "Spike CLI + Ollama tunnel" (composition-root script with `--repo/--range/--lang`; idempotent `tunnel` skipping `:11434` if up; `dev`; params from `.env`; assembly-only guard; verify = `make dev` summary + no duplicate tunnel on second run). Spec note exists and agrees. This is the milestone that makes the vertical slice hand-runnable — clear linkage.
- **Skill-context (`.ai-factory/skill-context/aif-review/SKILL.md`):** not present — no project-specific review overrides to apply.

## Review-1 Issues — Resolution Check

- **#1 (blocking) `ModuleNotFoundError` on bare-path invocation → RESOLVED.** The plan now mandates `uv run python -m scripts.summarize_range` everywhere (invocation-convention header, Task 1 docs/usage string, Task 3 `dev` target) and explicitly forbids the bare path and any `sys.path` bootstrap. Re-verified empirically:
  - `uv run python -m scripts._probe2` → `path0=<project root>`, `IMPORT_OK`
  - `uv run python scripts/_probe2.py` → `path0=<...>/scripts`, `FAIL ModuleNotFoundError No module named 'src'`
  - Confirmed `-m` works with `scripts/` as a namespace package (no `__init__.py` needed).
- **#2 (medium) hard `include .env` breaks `install`/`run` when `.env` absent → RESOLVED.** Task 2 now specifies the optional `-include .env` + `export` form and explains why, confining `.env` dependence to the `tunnel`/`dev` path.
- **SSH user (advisory) → RESOLVED.** Task 2 states the convention explicitly: no `SSH_USER` var; user is encoded in `SSH_HOST` (`user@host`) or via `~/.ssh/config`; the `ssh ... $(SSH_HOST)` command carries no separate user component.
- **Idempotency probe / exit codes (advisory) → RESOLVED.** Task 2 branches on one line (`nc -z localhost 11434 || ssh ...`) with `lsof` as an acceptable fallback, and calls out the separate-shell-per-recipe-line constraint.
- **Startup race (advisory) → ACKNOWLEDGED.** Task 3 notes that `ssh -f -N` backgrounds only after the forward is established, flagging only a low-likelihood first-run flake.
- **`--range` dest (advisory) → ADDRESSED.** Task 1 documents that `args.range` does not shadow the `range` builtin; re-verified: `argparse` parses `--range HEAD~3..HEAD` to `args.range` correctly.

## Verified — Correct Assumptions (re-confirmed against current source)

- `get_settings()` ← `src/core/config.py` ✓ (returns `Settings` with `ollama_url/ollama_model/ollama_api_key` + `ssh_host/ssh_port/ssh_key`).
- `GitCommitCollector().collect(repo_path, rev_range) -> CommitContext` ← `src/commits/collector.py` ✓ (positional `(args.repo, args.range)` match).
- `OllamaClient(base_url, model, api_key=None, timeout=120.0)` ← `src/llm/client.py` ✓ (positional `(settings.ollama_url, settings.ollama_model, settings.ollama_api_key)` is exact).
- `Summarizer(llm, prompt).summarize(context, lang="ru")` is `async` ← `src/summarization/service.py` ✓ → `asyncio.run(...)` correct; `print(...)` of the returned `str` correct.
- `PromptBuilder()` ← `src/summarization/prompt.py` ✓ (no-arg constructor).
- `.env.example` carries `OLLAMA_URL/OLLAMA_MODEL/OLLAMA_API_KEY/SSH_HOST/SSH_PORT/SSH_KEY` ✓ — no new keys required; `.env` is gitignored (secrets stay uncommitted).
- Existing `Makefile` has `install`/`run` under `.PHONY` ✓ — Task 3's "keep intact and update `.PHONY`" is accurate.

## Critical Issues

None.

## Minor / Advisory (non-blocking, no plan change required)

- **Probe tool availability.** If `nc` is absent, `nc -z ...` exits non-zero and the tunnel opens even when `:11434` is already up (harmless: the second forward fails to bind and exits, but prints an error). The plan already offers `lsof -i :11434` as a fallback, so the implementer can choose the tool present on the dev machine. Acceptable for a dev-only spike target.
- **`dev` omits `--lang`.** Task 3 runs the spike without `--lang`, relying on the `ru` default — consistent with the "dev branch is RU only" product rule and the milestone verify ("coherent RU summary"). Intentional, not a gap.
- **`export` + pydantic precedence.** `-include .env` + `export` surfaces `OLLAMA_URL` etc. as real env vars while pydantic-settings also reads `.env` via `env_file`. Both sources are the same file, so there is no precedence conflict. No action needed.

## Positive Notes

- The invocation-convention header is an exemplary response to review 1: it names the exact failure mode, the root cause (no `[build-system]` → `src` not installed as a package), the empirically-confirmed fix, and pins it to all three call sites plus the note. This is the right way to close a blocking review finding.
- Tunnel kept strictly a dev-only Makefile concern, out of application code — matches ARCHITECTURE's LLM-boundary/dev-concern separation precisely.
- Anti-pattern guardrails restated per task (assembly-only root, secrets only from `.env`, idempotent tunnel) and tied back to ARCHITECTURE and the spec note.
- Dependency ordering (Task 1 → 2 → 3) and the double-`make dev` idempotency verify are well specified.
- The "Note sync" section correctly designates the `-m` module form as source of truth over the stale bare-path command in the note, without inventing new behavior.

## Verdict

All review-1 findings are resolved and independently re-verified against the current codebase. API wiring, import strategy, Makefile `.env` handling, and SSH conventions are all correct. The plan is implementation-ready.

PLAN_REVIEW_PASS
