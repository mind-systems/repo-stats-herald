# Plan: Spike CLI + Ollama tunnel

## Context
Wires the existing vertical slice (Settings → `GitCommitCollector` → `Summarizer(OllamaClient)`) into a hand-runnable CLI and gives `make dev`/`make tunnel` ergonomics so one command brings up the SSH tunnel to the server's Ollama and prints a Russian summary of a real commit range.

**Invocation convention (blocking correctness):** the project defines **no `[build-system]`** in `pyproject.toml`, so `uv sync` does not install `src` as a package. Running `python scripts/summarize_range.py` puts `scripts/` on `sys.path[0]` (not the project root), so `from src.core.config import ...` raises `ModuleNotFoundError: No module named 'src'`. **Always run the spike as a module from the project root: `uv run python -m scripts.summarize_range ...`** (confirmed to import correctly, needs no `scripts/__init__.py`, and keeps the composition root free of `sys.path` hacks). This form is mandatory in Task 1's docs, Task 3's `dev` target, and any manual verify.

## Settings
- Testing: no
- Logging: minimal
- Docs: no

## Tasks

### Phase 1: CLI composition root

- [x] **Task 1: Add `scripts/summarize_range.py` spike entrypoint**
  Files: `scripts/summarize_range.py`
  Create the composition root — the only place concretes are wired, assembly only, no business logic. Use stdlib `argparse` (do NOT add `typer`/other deps) with flags `--repo` (path), `--range` (rev range, e.g. `HEAD~3..HEAD`), and `--lang` (default `ru`). `argparse` maps `--range` to `args.range`; attribute access does not shadow the `range` builtin, so this is safe. In `main()`:
  1. `settings = get_settings()` (from `src.core.config`).
  2. `collector = GitCommitCollector()` (from `src.commits.collector`).
  3. `summarizer = Summarizer(OllamaClient(settings.ollama_url, settings.ollama_model, settings.ollama_api_key), PromptBuilder())` (imports from `src.llm.client`, `src.summarization.service`, `src.summarization.prompt`).
  4. `ctx = collector.collect(args.repo, args.range)`.
  5. `print(asyncio.run(summarizer.summarize(ctx, args.lang)))`.
  Guard against the composition-root anti-pattern: no parsing/collecting/summarizing logic beyond argument parsing and wiring — delegate everything to the injected classes; do NOT add a `sys.path` bootstrap (the module-run convention above makes it unnecessary). Follow the DI wiring shown in `ARCHITECTURE.md` (Layer/Feature Communication section) and the spec note `.ai-factory/notes/06-spike-cli-tunnel.md`. Keep imports absolute (`src.*`) matching existing modules. **The script is run as a module — `uv run python -m scripts.summarize_range` — never as a bare path** (see the invocation convention above). Any comment/usage string in the file must show the `-m` form.

### Phase 2: Makefile ergonomics

- [x] **Task 2: Add idempotent `tunnel` target to `Makefile`** (depends on Task 1)
  Files: `Makefile`
  Add a `tunnel` target that is idempotent: check whether `localhost:11434` is already listening and only open a tunnel if not. Because each recipe line is a separate shell, branch on the probe's exit status **on one line**, e.g. `nc -z localhost 11434 || ssh -f -N -i $(SSH_KEY) -p $(SSH_PORT) -L 11434:127.0.0.1:11434 $(SSH_HOST)` (`lsof -i :11434` is an acceptable fallback probe). Read `SSH_KEY`/`SSH_PORT`/`SSH_HOST` from `.env`. Load them with the **optional** include form so absent `.env` never aborts other targets:
  ```makefile
  -include .env   # leading dash: missing file is not an error
  export
  ```
  A hard `include .env` would break `install`/`run` on a fresh clone/CI where `.env` doesn't exist yet — use `-include`.
  **SSH user convention:** there is no `SSH_USER` var and none is to be added — the dev encodes the user in `SSH_HOST` (`SSH_HOST=user@1.2.3.4`) or relies on `~/.ssh/config`. The `ssh ... $(SSH_HOST)` command must carry no separate user component.
  Guard (hard requirement): the host IP / key path / any SSH secret must NEVER be hardcoded in the Makefile — they come only from `.env`. Add `tunnel` (and the new `dev` target) to `.PHONY`. Reference the exact command and idempotency guard in `.ai-factory/notes/06-spike-cli-tunnel.md`.

- [x] **Task 3: Add `dev` target to `Makefile`** (depends on Task 2)
  Files: `Makefile`
  Add a `dev` target that depends on `tunnel` then invokes the spike against this repo's recent history **using the module form**: `uv run python -m scripts.summarize_range --repo . --range HEAD~3..HEAD` (a bare `python scripts/summarize_range.py` path fails with `ModuleNotFoundError` — see the invocation convention). This is the milestone's verify path: `make dev` brings the tunnel up if absent and prints a coherent RU summary; a second `make dev` opens no duplicate tunnel (guaranteed by Task 2's idempotency check). With `ssh -f -N`, ssh backgrounds only after the local forward is established, so the port is normally ready before the script runs (low-likelihood first-run flake only). Keep the existing `install`/`run` targets intact and update `.PHONY` accordingly.

## Note sync
The spec note `.ai-factory/notes/06-spike-cli-tunnel.md` Verify section currently shows the failing bare-path command (`scripts/summarize_range.py ...`) and the optional `spike:` target. Treat the `-m scripts.summarize_range` module form as the source of truth over the note wherever they differ; no behavior in the note changes, only the invocation string.
