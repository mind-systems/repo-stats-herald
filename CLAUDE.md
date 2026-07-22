What the service does and how each part behaves is specified under [docs/spec/](docs/spec-overview.md); this file is how to work in the code.

## Status

Only the summarization slice runs today: commit collection (`src/commits/`), the LLM boundary (`src/llm/`), and the summarizer (`src/summarization/`), wired by hand in `scripts/summarize_range.py` and exercised through the eval harness. `src/main.py` is a bare FastAPI app exposing `GET /health`. The webhook receiver, delivery, releases, and the internal protocol are specified but not built — treat their docs as the target contract, not existing code.

## Stack

- **Python 3.12 · FastAPI / uvicorn** — the service (`/health` today; webhook receiver in the target)
- **uv** — packaging and task runs
- **Ollama** via **httpx** — LLM generation and, in the target, embeddings; over the SSH tunnel in dev, co-located in prod
- **Postgres + pgvector** — Herald's own database: the knowledge store's vector search plus relational state (target; `herald_database` locally)
- **pydantic-settings** — typed config from env (`src/core/config.py`)
- **Telegram Bot API** — delivery (target)

## Commands

```bash
make install    # uv sync
make run        # uvicorn src.main:app --reload --port 8000
make tunnel     # SSH-forward Ollama to localhost:11434 (idempotent; params from .env.dev)
make dev        # tunnel + summarize HEAD~3..HEAD of this repo
make eval       # tunnel + run the eval harness
```

The SSH tunnel is a **local-dev** concern only: during development Ollama runs on a remote host reachable through the tunnel, so `make tunnel` is a prerequisite for any local run that touches the LLM (params in `.env.dev`, see `.env.example`). In the deployed setup the service sits next to Ollama on the server and reaches it on `localhost` — no tunnel.

### First-time setup — database

Herald uses its own Postgres database with the `vector` extension (pgvector), for the knowledge store and relational state. Once per machine:

```bash
# 1. Install pgvector for the SAME Postgres major your server runs. On a Homebrew
#    multi-major box, build from source against that server's pg_config:
#      git clone https://github.com/pgvector/pgvector && cd pgvector
#      make install PG_CONFIG=/usr/local/opt/postgresql@17/bin/pg_config
# 2. Create Herald's role, database, and extension:
psql -d postgres -c "CREATE ROLE herald_username LOGIN PASSWORD 'herald_password';"
psql -d postgres -c "CREATE DATABASE herald_database OWNER herald_username;"
psql -d herald_database -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

Connection params live in `.env.dev` (`POSTGRES_*`); see `.env.example`. In production the database ships as a pgvector image in Herald's container set.

## Architecture

**Pattern:** feature-modular, object-oriented with constructor dependency injection. Each feature is a self-contained package under `src/` that owns its models and services; cross-cutting infrastructure lives in dedicated infra modules. Concrete implementations are wired only at a **composition root** — a `scripts/*.py` entrypoint for the hand-runnable slice today, `src/main.py` for the web app in the target. Full dependency rules and the module template live in `.ai-factory/ARCHITECTURE.md`.

| Path | Purpose |
|------|---------|
| `src/core/` | Cross-cutting infra — `Settings` (pydantic-settings) + `get_settings()`; `create_pool()` (asyncpg pool with the pgvector `vector` codec) |
| `src/llm/` | Model-agnostic LLM boundary — `LLMClient` (ABC) + `OllamaClient` (httpx) |
| `src/knowledge/` | `chunks` pgvector schema (`schema.sql`) + `Chunk` value object + `KnowledgeStore` (ABC) / `PgVectorStore` |
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

The **architecture** — the intent→change→outcome model and the seams — is in [docs/architecture.md](docs/architecture.md). The behavioral spec lives in [docs/spec/](docs/spec-overview.md) — start at the overview. Forward-looking design concepts live in [docs/concepts/](docs/concepts/source-strategy-profiles.md).

| Doc | What it covers |
|-----|-----------------|
| [Overview](docs/spec-overview.md) | Spec entrance — end-to-end flow, actors, design spine |
| [Ingestion & Authorization](docs/spec/ingestion.md) | GitHub App webhook, installation as trust boundary, serve-allowlist |
| [Understanding](docs/spec/understanding.md) | Per-project knowledge model (RAG) + the project graph |
| [Narration](docs/spec/narration.md) | Feature-level notes, context sources, cross-project ripple, reports, languages |
| [Conversation](docs/spec/conversation.md) | Asking Herald about a project — questions answered from its memory by the reasoner |
| [Replay](docs/spec/replay.md) | Backtest over an existing history — simulated time, active-day reports, tag milestones |
| [Delivery](docs/spec/delivery.md) | Branch role, channels, delivery plan, versioning, internal protocol |
| [Configuration](docs/spec/configuration.md) | The resolver seam, global settings, database, multi-tenant evolution |
