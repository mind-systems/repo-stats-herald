# CLAUDE.md

## Purpose

A service that listens for GitHub push events, generates human-readable summaries of changes using an LLM, and delivers them to the right place depending on the branch. Acts as a press secretary between the development process and the outside world.

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

- **FastAPI** — webhook receiver
- **Ollama** — LLM summarization (runs on the host server)
- **asyncpg** — not used directly; apps own their own DBs
- **Telegram Bot API** — dev branch delivery
- **Docker** — packaged as a container
