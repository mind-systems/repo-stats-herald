What the service does and how each part behaves is specified under [docs/behavior/](docs/behavior-overview.md); this file is how to work in the code.

## Status

Phases 1–12 ship: push ingestion behind a GitHub App, the repo mirror, both memories and their retrieval, the reasoner and narration, the reporting engine, versioning, GitHub releases, Telegram delivery, and the internal changelog protocol. `src/main.py` assembles all of it at startup and mounts the webhook receiver. Production packaging, the conversational surface, historical replay, and multi-tenant operation are specified but not built — treat their docs as the target contract, not existing code.

## Stack

- **Python 3.12 · FastAPI / uvicorn** — the service: the GitHub webhook receiver and `GET /health`
- **uv** — packaging and task runs
- **Ollama** via **httpx** — LLM generation and embeddings; over the SSH tunnel in dev, co-located in prod
- **Postgres + pgvector** — Herald's own database: the knowledge and episodic stores' vector search plus relational state (`herald_database` locally)
- **pydantic-settings** — typed config from env (`src/core/config.py`)
- **Telegram Bot API** — delivery (target)

## Commands

```bash
make install    # uv sync
make run        # uvicorn src.main:app --reload --port 8000
make test       # uv run pytest
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
| `src/github/` | GitHub App auth (`GitHubAppAuth`, per-org installation tokens with a single-flight cache) + `RepoMirror` (per-repo bare clone, one worktree per operation) |
| `src/knowledge/` | `chunks` pgvector schema (`schema.sql`) + `Chunk` value object + `KnowledgeStore` (ABC) / `PgVectorStore` |
| `src/episodic/` | `episodic_entries` pgvector schema (`schema.sql`, append-only) + `EpisodicEntry` value object + `EpisodicStore` (ABC) / `PgEpisodicStore` |
| `src/commits/` | `Commit` / `CommitContext` value objects + `GitCommitCollector` (read-only `git log`) |
| `src/summarization/` | `PromptBuilder` (prompt text) + `Summarizer` (orchestration) |
| `src/ingestion/` | Webhook receiver — signature verification, push and installation parsing, `ServedRepoStore`, `EpisodicWriter`, background fan-out |
| `src/graph/` | `project_edges` schema + `Edge` / `EdgeKind` + `ProjectGraph` (ABC) / `PgProjectGraph` + `CoordinationSeeder` |
| `src/reasoning/` | `Reasoner` over both memories + the Q&A and narration prompt builders + `Localizer` (ABC) / `PivotLocalizer` / `NativeLocalizer` / `LLMTranslator` |
| `src/routing/` | `BranchRole` + `role_for_branch` + `DeliveryPlan` / `DeliveryPlanResolver` |
| `src/versioning/` | `Version` value object + `Versioner` — the next version from the repo's own tags, back-merge skip |
| `src/changelog/` | Report engine — `Report`, the `ReportSection` implementations, `ReportWindow` (`TimeWindow`, `SinceDeployWindow`), and `release_report` |
| `src/delivery/` | Channel clients — `TelegramClient`, `GitHubReleaseClient`, `ChangelogClient` — plus `DeliveryService` |
| `scripts/` | Composition-root entrypoints for offline runs (`summarize_range`, `eval`) |
| `evals/` | Eval fixtures, references, and outputs |
| `src/main.py` | Web-app composition root — assembles every collaborator at startup and mounts the webhook receiver; also serves `GET /health` |

## Patterns to follow

- **Wire concretes only at the composition root.** Feature and service classes receive abstractions through their constructor; they never construct a concrete client. `Summarizer` takes an `LLMClient`, not an `OllamaClient`.
- **Features depend on infra, never on each other.** A feature imports from `core/` and `llm/`, never another feature's internal files. If feature B needs feature A, it depends on A's public class.
- **The LLM seam stays model-agnostic.** `LLMClient` names no Ollama concept, so the backend swaps (Ollama today, hosted later) without touching feature code. Timeouts and transport errors raise — never a silently empty summary.
- **Config is read once at the root and injected.** `get_settings()` is called at the composition root; concrete clients take primitives (`ollama_url`, `ollama_model`). Features never read env directly.
- **Owned details stay inside the owning class.** Prompt strings live in `PromptBuilder`, git-command details in `GitCommitCollector`, HTTP specifics in `OllamaClient` — not inline in callers.
- **Secrets and host details come only from env.** Ollama URL, SSH host/key, tokens — always through `Settings`, never in committed code.

## Verification — eval harness

Summary quality is checked against fixed cases, not eyeballed. `evals/cases.yaml` holds cases that each declare a `type`; the runner dispatches by type to a registered handler and writes one `evals/out/<case>.md` per case, with stable filenames. Fields vary by type — a `summary` case carries `{repo, range, lang}`, a `distill` case a `root`, a `reasoner` case a `query`, a `localize` case a `langs` list. `evals/reference/<case>.md` holds user-authored good notes, never fabricated. The harness writes output and does not compare: a run's quality is judged by a person reading an output against its reference. Run any prompt or model change through the harness.

## Logging

Log through Python's `logging` module with structured output; level via the `LOG_LEVEL` env var. Never log with `print`.

## Documentation

The **architecture** — the intent→change→outcome model and the seams — is in [docs/architecture.md](docs/architecture.md). The behavioral spec lives in [docs/behavior/](docs/behavior-overview.md) — start at the overview. Forward-looking design concepts live in [docs/concepts/](docs/concepts/source-strategy-profiles.md).

| Doc | What it covers |
|-----|-----------------|
| [Architecture](docs/architecture.md) | The domain shape — how pushes become understanding and narration |
| [Overview](docs/behavior-overview.md) | Spec entrance — end-to-end flow, actors, design spine |
| [Ingestion & Authorization](docs/behavior/ingestion.md) | GitHub App webhook, installation as trust boundary, serve-allowlist |
| [Understanding](docs/behavior/understanding.md) | Per-project knowledge model (RAG) + the project graph |
| [Coordination-root format](docs/behavior/coordination-root-format.md) | The `CLAUDE.md` shape a coordination root declares — member table, edge kinds, seeding lifecycle |
| [Narration](docs/behavior/narration.md) | Feature-level notes, context sources, cross-project ripple, reports, languages |
| [Conversation](docs/behavior/conversation.md) | Asking Herald about a project — questions answered from its memory by the reasoner |
| [Replay](docs/behavior/replay.md) | Backtest over an existing history — simulated time, active-day reports, tag milestones |
| [Delivery](docs/behavior/delivery.md) | Branch role, channels, delivery plan, versioning, internal protocol |
| [Configuration](docs/behavior/configuration.md) | The resolver seam, global settings, database, multi-tenant evolution |
| [Code-derived understanding](docs/concepts/code-derived-understanding.md) | How a code-only project is understood at feature level, not classes |
| [Derivation modes](docs/concepts/derivation-modes.md) | Refines how the derivation engine chooses its source over a repo's history |
| [Intent distillation](docs/concepts/intent-distillation.md) | Distills a change's intent once at ingest when no anchor exists |
| [Product scope](docs/concepts/product-scope.md) | Introduces a product grouping and a multi-tenant ownership root |
| [Source-strategy profiles](docs/concepts/source-strategy-profiles.md) | How source strategies become a registry when a third shape appears |
| [Version increment policy](docs/concepts/version-increment-policy.md) | Turns the fixed version increment into a reasoner-judged policy seam |
