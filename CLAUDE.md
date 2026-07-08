# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository. What the service does and how each part behaves is specified under [docs/spec/](docs/spec-overview.md); this file is how to work in the code.

## Status

Only the summarization slice runs today: commit collection (`src/commits/`), the LLM boundary (`src/llm/`), and the summarizer (`src/summarization/`), wired by hand in `scripts/summarize_range.py` and exercised through the eval harness. `src/main.py` is a bare FastAPI app exposing `GET /health`. The webhook receiver, delivery, releases, and the internal protocol are specified but not built — treat their docs as the target contract, not existing code.

## Commands

```bash
make install    # uv sync
make run        # uvicorn src.main:app --reload --port 8000
make tunnel     # SSH-forward Ollama to localhost:11434 (idempotent; params from .env.dev)
make dev        # tunnel + summarize HEAD~3..HEAD of this repo
make eval       # tunnel + run the eval harness
```

The SSH tunnel is a **local-dev** concern only: during development Ollama runs on a remote host reachable through the tunnel, so `make tunnel` is a prerequisite for any local run that touches the LLM (params in `.env.dev`, see `.env.example`). In the deployed setup the service sits next to Ollama on the server and reaches it on `localhost` — no tunnel.

## Architecture

**Pattern:** feature-modular, object-oriented with constructor dependency injection. Each feature is a self-contained package under `src/` that owns its models and services; cross-cutting infrastructure lives in dedicated infra modules. Concrete implementations are wired only at a **composition root** — a `scripts/*.py` entrypoint for the hand-runnable slice today, `src/main.py` for the web app in the target. Full dependency rules and the module template live in `.ai-factory/ARCHITECTURE.md`.

| Path | Purpose |
|------|---------|
| `src/core/` | Cross-cutting infra — `Settings` (pydantic-settings) + `get_settings()` |
| `src/llm/` | Model-agnostic LLM boundary — `LLMClient` (ABC) + `OllamaClient` (httpx) |
| `src/commits/` | `Commit` / `CommitContext` value objects + `GitCommitCollector` (read-only `git log`) |
| `src/summarization/` | `PromptBuilder` (prompt text) + `Summarizer` (orchestration) |
| `scripts/` | Composition-root entrypoints for offline runs (`summarize_range`, `eval`) |
| `evals/` | Eval fixtures, references, and outputs |
| `src/main.py` | Web-app composition root — `GET /health` today; the webhook receiver in the target |

## Patterns to follow

- **Wire concretes only at the composition root.** Feature and service classes receive abstractions through their constructor; they never construct a concrete client. `Summarizer` takes an `LLMClient`, not an `OllamaClient`.
- **Features depend on infra, never on each other.** A feature imports from `core/` and `llm/`, never another feature's internal files. If feature B needs feature A, it depends on A's public class.
- **The LLM seam stays model-agnostic.** `LLMClient` names no Ollama concept, so the backend swaps (Ollama today, hosted later) without touching feature code. Timeouts and transport errors raise — never a silently empty summary.
- **Config is read once at the root and injected.** `get_settings()` is called at the composition root; concrete clients take primitives (`ollama_url`, `ollama_model`). Features never read env directly.
- **Owned details stay inside the owning class.** Prompt strings live in `PromptBuilder`, git-command details in `GitCommitCollector`, HTTP specifics in `OllamaClient` — not inline in callers.
- **Secrets and host details come only from env.** Ollama URL, SSH host/key, tokens — always through `Settings`, never in committed code.

## Verification — eval harness

Summary quality is checked against fixed cases, not eyeballed. `evals/cases.yaml` holds `{repo, range, lang}` cases, `evals/reference/<case>.md` holds user-authored good notes (never fabricated), and `make eval` writes one `evals/out/<case>.md` per case with stable filenames for diffing against the references. Run any prompt or model change through the harness.

## Logging

Log through Python's `logging` module with structured output; level via the `LOG_LEVEL` env var. Never log with `print`.

## Documentation

The full spec lives in [docs/spec/](docs/spec-overview.md) — start at the overview.

| Doc | What it covers |
|-----|-----------------|
| [Overview](docs/spec-overview.md) | Spec entrance — end-to-end flow, actors, design spine |
| [Ingestion & Authorization](docs/spec/ingestion.md) | GitHub App webhook, installation as trust boundary, permissions |
| [Summarization](docs/spec/summarization.md) | Commit collection, two-stage digest, generation languages |
| [Delivery & Routing](docs/spec/delivery.md) | Branch role, the three channels, delivery plan |
| [Versioning](docs/spec/versioning.md) | Semver, `-rc` on staging, back-merge skip |
| [Internal Protocol](docs/spec/internal-protocol.md) | Changelog contract toward integrated apps |
| [Configuration](docs/spec/configuration.md) | The resolver seam, global settings, multi-tenant evolution |
