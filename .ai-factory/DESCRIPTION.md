# repo-stats-herald

## Overview

A service that listens for GitHub push events across all repositories in an organization, generates human-readable summaries of changes using a local LLM (Ollama), and delivers them to the appropriate destination based on the branch.

Acts as a press secretary between the development process and the outside world — collecting what happened, summarizing it in natural language, and routing it to the right audience.

## Core Features

- Receives GitHub push webhooks via GitHub Actions (a `.github/workflows/herald.yml` dropped into each repo)
- Summarizes commits using Ollama (`qwen2.5:14b-instruct-q4_K_M`) running on the host server
- Delivers summaries to Telegram for all branches except `staging` and `master`
- For `staging` and `master`: delivers to Telegram (with version header) + calls the target app's internal changelog endpoint + creates a GitHub release/pre-release
- Accumulates daily digests; staging/master release notes are built from accumulated commits since last deploy to that environment
- Supports multiple languages per app — each app declares its supported languages, summaries are generated in all of them

## Tech Stack

- **Language:** Python
- **Framework:** FastAPI
- **LLM:** Ollama (local, via `http://172.17.0.1:11434`)
- **GitHub:** GitHub App (org-level, read commits + write releases)
- **Delivery:** Telegram Bot API
- **Deploy:** Docker container

## Internal Protocol

Each integrated application exposes two internal endpoints on a dedicated internal port (no API keys — restricted to internal network):

```
GET  /internal/changelog/config   → { "languages": ["ru", "en"] }
POST /internal/changelog/entry    → { version, environment, summary_ru, summary_en?, github_url }
```

## Architecture

See `.ai-factory/ARCHITECTURE.md` for detailed architecture guidelines.
Pattern: Structured Modules (Technical Layers)

## Versioning

- `master` push → semver tag + GitHub release
- `staging` push → same version with `-rc` suffix + GitHub pre-release
- Back-merges from master to staging are detected and skipped (no version bump)

## Branch → Delivery Matrix

| Branch | Telegram | App changelog | GitHub release |
|--------|----------|---------------|----------------|
| any other | ✓ RU, no version | — | — |
| `staging` | ✓ RU, `v1.2.0-rc` header | ✓ | pre-release |
| `master` | ✓ RU, `v1.2.0` header | ✓ | release |
