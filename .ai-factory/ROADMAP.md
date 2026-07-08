# Project Roadmap

> A press secretary between the dev process and the outside world: listens for GitHub pushes, summarizes changes with a local LLM, and routes human-readable release notes by branch.

## Active tasks

> Above `---STOP---`: atomic, orchestrator-ready tasks — each a contract line plus a spec note. Below the stop: the phase backlog; each phase is decomposed into tasks above as we reach it, and checked off once all its tasks are done. The orchestrator processes tasks above the stop only.

### Phase 1 — Summarizer spike & eval harness

- [x] **Project scaffold** — repo has no runnable app (only `.ai-factory/`, `CLAUDE.md`, `.mcp.json`); nothing proves the toolchain boots. Init a uv application (`pyproject.toml`, py3.12, fastapi+uvicorn — no build-system), `src/__init__.py`, `src/main.py` with `app` + `GET /health → {"status":"ok"}`, and a minimal `Makefile` (`install`/`run`). Skeleton only, no logic. Verify: `make run` boots, `curl :8000/health`=200. Spec: `.ai-factory/notes/01-project-scaffold.md`. [4m 39s]
- [x] **Settings layer** — no typed home for Ollama connection or dev SSH-tunnel params. Add `src/core/config.py` with `Settings(BaseSettings)` (pydantic-settings) — `ollama_url/ollama_model/ollama_api_key?` + `ssh_host/ssh_port/ssh_key` — and `get_settings()`, plus a `.env.example` documenting keys with no secrets. Guard: secrets only from env, host IP never in committed code. Spec: `.ai-factory/notes/02-settings-layer.md`. [8m 6s]
- [x] **commits/ feature** — no representation of commits and no way to read history. Add `src/commits/models.py` (immutable `Commit`, `CommitContext`) and `src/commits/collector.py` (`GitCommitCollector.collect(repo_path, rev_range) -> CommitContext`) shelling read-only `git log --stat` with a NUL field separator. Local git only, no GitHub API. Guard: never mutate/network; empty ranges & merge commits must not crash. Verify: `HEAD~3..HEAD` on this repo → populated context. Spec: `.ai-factory/notes/03-commits-feature.md`. [12m 50s]
- [x] **llm/ boundary** — no model-agnostic seam; calling Ollama from business logic would hardwire the 14B model. Add `src/llm/client.py` with `LLMClient(ABC).generate(prompt)->str` and `OllamaClient(LLMClient)` (httpx → `{ollama_url}/api/generate`, bearer only if key set). Guard: `LLMClient` names no Ollama concept; timeouts/errors raise, never a silent empty string. Verify: through the tunnel, `generate` returns non-empty text. Spec: `.ai-factory/notes/04-llm-boundary.md`. [4m 39s]
- [x] **summarization/ feature** — nothing turns a `CommitContext` into release notes (the core value). Add `src/summarization/prompt.py` (`PromptBuilder.build(context, lang)`) and `src/summarization/service.py` (`Summarizer(llm: LLMClient, prompt: PromptBuilder).summarize(context, lang="ru")`). Guard: constructor DI — `Summarizer` never builds a concrete client; prompt text stays in `PromptBuilder`, not inline. Verify: real context → coherent RU summary referencing the actual changes. Spec: `.ai-factory/notes/05-summarization-feature.md`. [4m 53s]
- [x] **Spike CLI + Ollama tunnel** — the slice isn't runnable by hand and Ollama is only reachable over SSH. Add `scripts/summarize_range.py` (composition root: Settings → `GitCommitCollector` → `Summarizer(OllamaClient(...))`, `--repo/--range/--lang`) and `Makefile` `tunnel` (idempotent: skip if `:11434` already up, else `ssh -f -N -L`, params from `.env`) + `dev`. Guard: assembly only; host IP never in the Makefile. Verify: `make dev` → summary of `HEAD~3..HEAD`; second `make dev` opens no duplicate tunnel. Spec: `.ai-factory/notes/06-spike-cli-tunnel.md`. [9m 40s]
- [x] **Eval harness** — summary quality can only be eyeballed once; prompt/model changes have no signal. Add `evals/cases.yaml` (fixed `{repo,range,lang}` cases), `evals/reference/<case>.md` (user-authored good notes), and `scripts/eval.py` with `EvalRunner` reusing the same `Summarizer`/`GitCommitCollector`, writing `evals/out/<case>.md` per case. Guard: offline, stable filenames for diffing; references authored by user, never fabricated. Verify: one output file per case. Spec: `.ai-factory/notes/07-eval-harness.md`. [7m 35s]

---STOP---

## Phases (backlog)

### Phase 2 — Structure-aware context collection

The summarizer works today from commit messages, changed paths, and diffstats — the
model infers intent from thin input. This phase enriches `commits/` context with PR
titles and bodies and a short per-repo project map, so quality comes from what is fed
in rather than the model guessing. Extends the existing `commits/` collection and the
`PromptBuilder` context; needs no service plumbing — it improves the hand-runnable
slice and is measured through the existing eval harness. See
[docs/summarization.md](../docs/summarization.md).

### Phase 3 — Two-stage summarization pipeline

A single LLM call reasoning over a whole push strains the 14B model. This phase splits
summarization into stage one (atomic per-commit/PR summaries, run in parallel) and
stage two (aggregate into a digest), keeping each call in the model's competence zone
and yielding key-moment digests rather than per-commit logs. Swappable at the
`LLMClient` boundary. Builds on Phase 2's richer context. See
[docs/summarization.md](../docs/summarization.md).

### Phase 4 — Herald core service (ingestion → Telegram)

Nothing turns a real push into a delivered note — the summarizer runs only by hand.
This phase stands up the FastAPI webhook receiver and the first end-to-end path:
push → summary → Telegram (language a configured default, RU, resolved through the
seam — not hard-coded). Pushes arrive as the GitHub App's single signed
webhook (not a per-repo `herald.yml`); signature verification and the installation
scope are the authorization and anti-spam boundary. Branch-role resolution
(`master`/`main` → release, `staging`, else `dev`) and the delivery-plan resolver seam
land here, with the `organization → Telegram channel` map behind it. Requires
provisioning the GitHub App (contents/metadata/pull_requests) and the Telegram bot.
Only the Telegram channel fires in this phase — releases and changelog come later.
See [docs/ingestion.md](../docs/ingestion.md), [docs/delivery.md](../docs/delivery.md),
[docs/configuration.md](../docs/configuration.md).

### Phase 5 — Digest accumulation

Release notes for staging and master must reflect everything since the last deploy,
not a single push. This phase persists per-branch digests and accumulates commits
since the previous deploy to each environment, so notes are built from collected
history. Blocked on the core service (Phase 4) producing digests to persist. See
[docs/summarization.md](../docs/summarization.md).

### Phase 6 — GitHub releases & versioning

The release channel and the version lifecycle. On `staging` and the default branch,
cut a GitHub release (language a configured default, EN) with a semver tag: a full
release on `master`/`main`, a
`-rc` pre-release on `staging`. Detect back-merges from the default branch into
staging (incoming SHAs already released) and skip the version bump. Adds tag and
release creation through the GitHub App's `contents: write`. Blocked on the core
service (Phase 4). See [docs/versioning.md](../docs/versioning.md),
[docs/delivery.md](../docs/delivery.md).

### Phase 7 — Internal protocol & first app integration

The third channel — writing notes into an integrated app's own changelog store.
Hand-write the two internal endpoints (`GET /internal/changelog/config`,
`POST /internal/changelog/entry`) into one real app (mind_api already has a
`src/changelog/` feature to build on), storing entries in its own Postgres, reachable
on the internal network with no API keys. Herald gains the `repository → changelog
app` map and per-app language negotiation — it generates the languages the app
declares. Freeze the contract as a single `contract/changelog.openapi.yaml`, the one
cross-cutting invariant. Blocked on releases (Phase 6) supplying the version and
github_url an entry carries. See [docs/internal-protocol.md](../docs/internal-protocol.md).

### Phase 8 — Extracted changelog SDK

After a second manual integration reveals what actually repeats, extract the thin
shared part (table migration + write router) into `sdk/nestjs/` and `sdk/fastapi/` in
this monorepo, consumed by git rather than a public registry. SDK extraction comes
last, once the contract has proven stable across two real integrations. Blocked on
Phase 7 and a second integration. See [docs/internal-protocol.md](../docs/internal-protocol.md).

### Phase 9 — Production deployment

Package Herald as a Docker container with clean env/config wiring (Ollama URL, GitHub
App creds and webhook secret, Telegram token), sitting next to Ollama on the server so
the SSH tunnel stays dev-only. Where it runs is the deployer's concern. Blocked on a
working end-to-end path (Phase 4). See [docs/configuration.md](../docs/configuration.md).

### Phase 10 — Quality feedback loop

Fold approved release notes back into the eval case set and the few-shot prompt so
quality compounds, and keep the `LLMClient` boundary swappable for a larger or hosted
model without re-platforming. Ongoing once notes are produced in production. See
[docs/summarization.md](../docs/summarization.md).

### Phase 11 — Multi-tenant configuration & GUI

Today routing state (org→channel, repo→app, branch roles) lives in environment/static
config behind the resolver seam. This phase grows the backing store from env →
database → a GUI where organizations self-manage their repositories, delivery
channels, and access rights, turning Herald into a service usable by many
organizations at once. Per-app access keys enter here, at the point apps are reached
across a network boundary rather than co-located. Depends only on the seam (Phase 4)
existing; deliberately deferred until single-tenant operation is proven. See
[docs/configuration.md](../docs/configuration.md).
