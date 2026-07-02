# Code Review: 06 — Spike CLI + Ollama tunnel

**Plan:** `.ai-factory/plans/06-spike-cli-ollama-tunnel.md`
**Changed code:** `scripts/summarize_range.py` (new), `Makefile` (modified)
**Also changed (non-code):** spec note, plan/plan-review artifacts — not reviewed for runtime behavior.

## Scope

Reviewed the two code artifacts in full against their collaborators: `src/core/config.py`, `src/commits/collector.py`, `src/commits/models.py`, `src/llm/client.py`, `src/summarization/service.py`, `src/summarization/prompt.py`, `pyproject.toml`, `.gitignore`.

## Correctness — verified against real source

- **Import path / invocation.** `pyproject.toml` has no `[build-system]`, so `src` is not installed as a package; `scripts/` has no `__init__.py`. Both the docstring and the `dev` target use `uv run python -m scripts.summarize_range`, which runs from the project root with the root on `sys.path[0]`, making `src.*` importable. The failing bare-path form is avoided everywhere. Correct.
- **DI wiring.** `Summarizer(OllamaClient(settings.ollama_url, settings.ollama_model, settings.ollama_api_key), PromptBuilder())` matches `OllamaClient(base_url, model, api_key=None, timeout=120.0)` and `Summarizer(llm, prompt)` positionally. `collector.collect(args.repo, args.range)` matches `collect(repo_path, rev_range)`. `summarize` is `async`, so `asyncio.run(...)` around it and `print(...)` of the returned `str` are correct.
- **Argparse.** `--range` uses `dest="range"`; `args.range` is a plain attribute and does not shadow the `range` builtin. `--lang` defaults to `ru`, consistent with the dev-branch RU-only rule and the milestone verify.
- **Composition-root discipline.** The script contains only argument parsing and wiring — no collecting/summarizing logic — honoring the architecture's "no logic in entry points" anti-pattern.
- **Secrets hygiene.** No host IP, key path, or user is present in the `Makefile` or the script; all SSH params come from `$(SSH_KEY)/$(SSH_PORT)/$(SSH_HOST)`. `.gitignore` ignores `.env`/`.env.*` while preserving `.env.example`, and `git ls-files` confirms `.env` is untracked. No secret is committed.
- **`.env` loading.** `-include .env` (leading dash) means a missing `.env` does not abort `make`, so `install`/`run` keep working on a fresh clone/CI. `export` surfaces the values to recipe shells; pydantic-settings reads the same `.env` via `env_file`, so the two sources agree — no precedence conflict.
- **Idempotent tunnel.** `nc -z localhost 11434 || ssh -f -N ...` on a single recipe line: port up → `nc` exits 0 → `ssh` skipped; port down → tunnel opens. Second `make dev` therefore opens no duplicate tunnel — the milestone's stated verify holds. `.PHONY` correctly lists `install run tunnel dev`.

## Non-blocking observations (no change required)

These were already surfaced and accepted during plan review; noting for completeness, none is a defect:

- **`nc` absence.** If `nc` is not installed, `nc -z ...` exits non-zero and the tunnel is (re)opened even when `:11434` is already up. Harmless — the duplicate local forward fails to bind and exits — and `lsof -i :11434` is offered as a fallback probe. Acceptable for a dev-only target.
- **First-run readiness.** `dev` runs the script immediately after `ssh -f -N`; `-f` backgrounds only once the local forward is established, so the port is normally ready. Low-likelihood first-run flake only.
- **Error surface.** A bad `--repo`/`--range` or an unreachable Ollama surfaces as an unhandled `CalledProcessError`/`httpx` traceback. Fine for a spike per the plan's "minimal logging" setting.

## Verdict

The implementation matches the twice-reviewed plan and every collaborator signature; import strategy, `.env` handling, secret hygiene, and tunnel idempotency are all correct. No correctness, security, or runtime-breakage findings.

REVIEW_PASS
