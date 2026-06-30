# Architecture: Structured Modules (Technical Layers)

## Overview

A modular service organized by technical layer. Each layer has a clear responsibility and only depends on layers below it. Chosen for this project because it is a focused single-purpose service with well-defined integrations (GitHub, Ollama, Telegram, internal app protocol) and no complex domain logic — clean layers keep the code navigable without over-engineering.

## Decision Rationale

- **Project type:** Internal webhook service, single responsibility
- **Tech stack:** Python, FastAPI
- **Key factor:** Small scope with multiple external integrations — layers separate routing, business logic, and external calls cleanly

## Folder Structure

```
src/
├── main.py                  # FastAPI app entrypoint
├── config.py                # Settings via env vars (pydantic-settings)
├── routes/                  # HTTP layer — webhook receivers, request validation
│   └── webhook.py
├── services/                # Business logic — orchestrates integrations
│   ├── pipeline.py          # Main dispatch pipeline (branch → delivery)
│   ├── summarizer.py        # Ollama interaction
│   ├── github.py            # GitHub API (commits, releases, tags)
│   ├── telegram.py          # Telegram Bot API delivery
│   └── changelog.py        # Internal app protocol (config + entry)
├── models/                  # Pydantic models (request/response schemas)
│   ├── webhook.py
│   └── changelog.py
└── utils/
    └── version.py           # Semver bump, back-merge detection

config.yml                   # Project registry (repos → app endpoints + languages)
Dockerfile
docker-compose.yml
.env.example
```

## Dependency Rules

- `routes/` → `services/` → external APIs (Ollama, GitHub, Telegram)
- `routes/` uses `models/` for request validation
- `services/` uses `models/` for data passing
- `config.py` is readable by any layer

- ✅ routes → services → external
- ✅ any layer → models, config, utils
- ❌ services → routes (no reverse dependency)
- ❌ one service → another service (use pipeline.py as orchestrator instead)

## Layer Communication

- Routes parse and validate the incoming webhook payload, then call `pipeline.py`
- `pipeline.py` determines branch type and orchestrates the correct service calls
- Services are stateless functions / thin classes — they receive data, call external APIs, return results
- No shared mutable state between services

## Key Principles

1. **Pipeline is the only orchestrator** — `services/pipeline.py` is the single place that knows the branch → delivery routing logic
2. **Services don't call each other** — `pipeline.py` composes them; services only talk to their own external dependency
3. **Config drives project registry** — adding a new repo means editing `config.yml`, not code
4. **Back-merge safety** — version bump is skipped if the commit SHA is already present in master; detected in `utils/version.py` before any release action

## Code Examples

### Route handler
```python
@router.post("/webhook")
async def github_webhook(request: Request, payload: WebhookPayload):
    verify_signature(request, settings.webhook_secret)
    await pipeline.dispatch(payload)
    return {"ok": True}
```

### Pipeline dispatch
```python
async def dispatch(payload: WebhookPayload):
    branch = payload.ref.removeprefix("refs/heads/")
    commits = await github.fetch_commits(payload)
    summary = await summarizer.summarize(commits, lang="ru")

    if branch not in ("staging", "master"):
        await telegram.send(summary)
        return

    app_config = await changelog.get_config(payload.repo)
    summaries = await summarizer.summarize_multilang(commits, app_config.languages)
    version = version_utils.next_version(branch)
    release_url = await github.create_release(payload.repo, version, summaries)
    await changelog.post_entry(payload.repo, version, summaries, release_url)
    await telegram.send(f"*{version}*\n\n{summaries['ru']}")
```

### Service — no cross-service calls
```python
# services/summarizer.py — only talks to Ollama
async def summarize(commits: list[Commit], lang: str) -> str:
    prompt = build_prompt(commits, lang)
    response = await ollama_client.post("/api/generate", json={"model": MODEL, "prompt": prompt})
    return response.json()["response"]
```

## Anti-Patterns

- ❌ Don't add routing logic inside services — branch/delivery decisions belong in `pipeline.py`
- ❌ Don't call `telegram.py` or `github.py` directly from routes — always go through pipeline
- ❌ Don't hardcode repo→app mappings in code — use `config.yml`
- ❌ Don't create a new version tag without checking for back-merge first
