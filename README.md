# repo-stats-herald

> A press secretary between the development process and the outside world.

Herald is an org-wide GitHub App that builds a standing understanding of each project
in an organization — what it is now and how it got there — from the project's own
curated docs and history, and narrates how its features progress with a local LLM. A
push updates Herald's memory; the story goes out as periodic reports and as versioned
release notes — to Telegram, GitHub releases, and each integrated app's own changelog
store.

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

- **Understands each project** — replays a project's pushes into two memories: a
  semantic model of what it is now, and an episodic log of how it changed. It reasons
  over these rather than summarizing files one shot at a time.
- **Narrates at the feature level** — a model-agnostic reasoner turns a change into
  prose about what moved and what it unblocks across the ecosystem, anchored on the
  roadmap tasks that shipped, not a raw commit log.
- **Reports on a cadence, releases on a milestone** — a served push updates memory and
  is not reported on its own; delivery fires as daily and weekly reports — each an
  ordered composition of content sections (a summary, a per-branch breakdown, more)
  assembled from configuration — and, on a push to `staging` or the default branch, a
  versioned release note.
- **Multi-channel, multi-language** — Telegram (RU), GitHub releases (EN), and each
  integrated app's changelog store (app-declared languages); a semver lifecycle with
  `-rc` pre-releases on staging, full releases on the default branch, back-merges
  skipped.
- **Org-wide by installation** — a single GitHub App installed on an organization
  authorizes every repo it covers; new repos are picked up without extra wiring.

## Example

```bash
uv run python -m scripts.summarize_range --repo . --range HEAD~3..HEAD --lang ru
```

Prints an LLM-generated summary of the given commit range — the summarization spike
that runs today.

## Status

The summarization spike runs today: commit collection, the LLM boundary, and the
summarizer, driven by hand through the CLI and checked by the eval harness. The
understanding model (the two memories and the reasoner), reports, releases, and the
internal protocol are specified and not built yet.

See [the specification](docs/spec-overview.md) for how each part behaves.
