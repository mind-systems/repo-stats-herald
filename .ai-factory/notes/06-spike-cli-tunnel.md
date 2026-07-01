# Spike CLI + Ollama Tunnel — End-to-End Runnable Slice

**Date:** 2026-07-01
**Source:** conversation context

## Key Findings

- The vertical slice (config → collect commits → summarize via Ollama) exists as parts but cannot be run by hand.
- This task adds the composition root as a CLI plus the `make dev` / `make tunnel` ergonomics, so a single command brings up the SSH tunnel to the server's Ollama and prints a Russian summary of a real commit range. This is the milestone's goal: run locally, hit the model, see a summary.

## Details

### Current state
Tasks 01–05 give a bootable app, `Settings`, `GitCommitCollector`, `OllamaClient`, and `Summarizer` — but no entrypoint wires them, and Ollama on the server is only reachable through an SSH tunnel.

### Target
- `scripts/summarize_range.py` — the composition root (the only place concretes are wired):
  ```python
  # args: --repo <path> --range <rev_range> --lang ru
  settings = get_settings()
  collector = GitCommitCollector()
  summarizer = Summarizer(
      OllamaClient(settings.ollama_url, settings.ollama_model, settings.ollama_api_key),
      PromptBuilder(),
  )
  ctx = collector.collect(repo, rev_range)
  print(asyncio.run(summarizer.summarize(ctx, lang)))
  ```
  Uses `argparse` (or `typer` if already pulled in — prefer stdlib `argparse` to avoid a dep). No business logic here — assembly only.
- `Makefile` gains:
  - `tunnel:` — **idempotent**. Guard first: if `localhost:11434` is already listening (`nc -z localhost 11434` or `lsof -i :11434`), do nothing; otherwise open a backgrounded tunnel:
    `ssh -f -N -i $(SSH_KEY) -p $(SSH_PORT) -L 11434:127.0.0.1:11434 $(SSH_HOST)`
    Read `SSH_KEY` / `SSH_PORT` / `SSH_HOST` from `.env` (never hardcode the host IP in the Makefile).
  - `dev:` → `tunnel` then run the app / or invoke the spike.
  - `spike:` (optional convenience) → `tunnel` then `uv run python scripts/summarize_range.py --repo . --range HEAD~3..HEAD`.

### Architecture notes
The CLI is a composition root exactly like `src/main.py` will be for the web app — the single wiring point where abstractions meet concretes. Everything below it stays free of instantiation decisions. The tunnel is a **dev-only** concern: on the server, herald runs in Docker and reaches Ollama directly via the server-side `OLLAMA_URL`, so nothing tunnel-related belongs in application code — it lives only in the Makefile.

### Guards
- `make tunnel` must be idempotent — never stack duplicate tunnels on repeated `make dev`.
- SSH connection params come from `.env`; the host IP / key path never enter committed files.
- CLI does assembly only — no parsing/collecting/summarizing logic inside the script beyond wiring.

### Verify
- With `.env` filled (real `SSH_*` + `OLLAMA_URL=http://localhost:11434`):
  `make dev` (or `make spike`) brings the tunnel up if absent, then
  `scripts/summarize_range.py --repo . --range HEAD~3..HEAD` prints a coherent RU summary of this repo's recent commits.
- Running `make dev` twice does not open a second tunnel.

## Open Questions

- Needs the developer's real SSH tunnel credentials (host, port, key path, user) in local `.env` before verification — supplied out-of-band, never committed.
