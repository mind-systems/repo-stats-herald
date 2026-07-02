# CLAUDE.md

## Purpose

A service that listens for GitHub push events, generates human-readable summaries of changes using an LLM, and delivers them to the right place depending on the branch. Acts as a press secretary between the development process and the outside world.

## Status

This page describes the **target contract**. What runs today: the summarization slice — commit collection (`src/commits/`), the LLM boundary (`src/llm/`), the summarizer (`src/summarization/`) — driven by hand via the CLI (`scripts/summarize_range.py`) and verified by the eval harness. The webhook receiver, delivery, releases, and the internal protocol are not built yet.

## Commands

```bash
make install    # uv sync
make run        # uvicorn src.main:app --reload --port 8000
make tunnel     # SSH-forward Ollama to localhost:11434 (idempotent; params from .env.dev)
make dev        # tunnel + summarize HEAD~3..HEAD of this repo
make eval       # tunnel + run the eval harness
```

Ollama runs on a remote host and is only reachable through the SSH tunnel — `make tunnel` is a prerequisite for any run that touches the LLM. Connection params live in `.env.dev` (see `.env.example`).

## Verification — eval harness

Summary quality is checked against fixed cases, not eyeballed: `evals/cases.yaml` holds `{repo, range, lang}` cases, `evals/reference/<case>.md` holds user-authored good notes (never fabricated), and `make eval` writes one `evals/out/<case>.md` per case with stable filenames for diffing against the references. Prompt or model changes must be run through the harness.

## How It Works

When a push happens to any tracked repository:

1. Collects commits since the last push to that branch
2. Sends them to Ollama for summarization in the required language(s)
3. Delivers the summary based on the branch:

| Branch | Delivery |
|--------|----------|
| any other branch | Telegram (RU, no version header) |
| `staging` | Telegram (RU, header: `v1.2.0-rc`) + app changelog store + GitHub pre-release |
| `master` | Telegram (RU, header: `v1.2.0`) + app changelog store + GitHub release |

Staging and master Telegram messages contain the same text as the release notes — just with a version header and rc/release marker. Summaries for staging and master accumulate from commits since the previous deploy to that environment.

## Languages

Each integrated app declares which languages it supports. The summary is generated in all declared languages. Dev branch is always RU only.

## Internal Protocol

Each integrated application exposes two internal endpoints on a dedicated internal port (no API keys — access is restricted to the internal network):

```
GET  /internal/changelog/config   → { "languages": ["ru", "en"] }
POST /internal/changelog/entry    → { version, environment, summary_ru, summary_en?, github_url }
```

Changelogs are stored in each app's own Postgres database and exposed to users as a "what's new" feed.

## Versioning

- `master` push → semver tag + GitHub release
- `staging` push → same version with `-rc` suffix + GitHub pre-release
- Back-merges from master to staging are detected and skipped (no version bump)

## GitHub Access

Uses a GitHub App (not personal tokens) installed on all tracked repositories. Permissions: `contents: read`, `metadata: read`, `releases: write`.

## Stack

- **FastAPI + uvicorn** — the service (webhook receiver in the target contract; `/health` today)
- **Ollama** — LLM summarization; lives on the server, where the deployed service will sit right next to it. The SSH tunnel exists only for dev, while the service runs locally for debugging
- **httpx** — Ollama HTTP client
- **pydantic-settings** — typed config from env (`src/core/config.py`)
- **Telegram Bot API** — delivery (target)
