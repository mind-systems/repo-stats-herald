# repo-stats-herald

> A press secretary between the development process and the outside world.

Herald listens for GitHub pushes across an organization's repositories, turns the
commits into human-readable release notes with a local LLM, and routes each note to
the right place depending on the branch — Telegram for day-to-day work, GitHub
releases and each app's own changelog store for staging and production.

## Quick Start

```bash
make install    # uv sync
make tunnel     # SSH-forward Ollama to localhost:11434 (params from .env.dev)
make dev        # summarize HEAD~3..HEAD of this repo through Ollama
```

Ollama runs on a remote host reachable only through the SSH tunnel, so `make tunnel`
is a prerequisite for anything that touches the LLM. Connection params live in
`.env.dev` (see `.env.example`).

## Key Features

- **Push-to-notes** — collects the commits behind a push and summarizes them as
  release notes, keyed to what actually changed.
- **Branch-aware routing** — a branch's role (dev, staging, release) decides which
  channels fire, in which language, and with which formatting.
- **Multi-channel delivery** — Telegram (RU), GitHub releases (EN), and each
  integrated app's own changelog store (app-declared languages).
- **Semver lifecycle** — real releases on the default branch, `-rc` pre-releases on
  staging, back-merges detected and skipped.
- **Org-wide by installation** — a single GitHub App installed on an organization
  authorizes every repo it covers; new repos are picked up without extra wiring.

## Example

```bash
uv run python -m scripts.summarize_range --repo . --range HEAD~3..HEAD --lang ru
```

Prints an LLM-generated summary of the given commit range — the same summarization
core the service runs on each push.

## Status

The summarization slice runs today (commit collection, the LLM boundary, the
summarizer), driven by hand through the CLI and checked by the eval harness. The
webhook receiver, delivery, releases, and the internal protocol describe the target
contract and are not built yet.
