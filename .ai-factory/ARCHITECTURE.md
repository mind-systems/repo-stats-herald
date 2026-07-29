# Architecture: Feature-Modular (OOP + DI)

## Overview

A modular application organized **by feature**, not by technical layer. Each feature is a self-contained package that owns its own models, services, and (where relevant) its router and external clients. Features communicate only through their public objects — never by reaching into another feature's internals. Cross-cutting infrastructure (config, the LLM boundary, later Telegram/GitHub clients) lives in dedicated infra modules that features depend on.

The style is object-oriented: behavior lives in classes with clear responsibilities, dependencies are passed in through constructors (dependency injection), and concrete implementations are wired together only at a **composition root** (`src/main.py` for the web app, a `scripts/*.py` entrypoint for the spike). This keeps layers visible, encapsulation intact, and the code out of spaghetti.

This mirrors the modular monolith used across the wider codebase (`mind_api` NestJS feature modules; `mind_mobile` `*Module/` + `Core/`), translated to Python/FastAPI.

## Decision Rationale

- **Project type:** Internal service with several external integrations (GitHub, Ollama, Telegram, internal app protocol)
- **Tech stack:** Python 3.12, FastAPI, uv
- **Key factor:** Feature boundaries (summarization, commits, delivery, releases, changelog) are natural and mostly independent; a feature-first layout keeps each concern encapsulated and swappable, and the OOP + DI discipline keeps the seams (especially the LLM boundary) clean and testable

## Folder Structure

```
src/
├── main.py              # composition root: FastAPI app + wiring, GET /health
├── core/                # cross-cutting infrastructure (config, shared base types)
│   └── config.py        # Settings (pydantic-settings), get_settings()
├── llm/                 # infra module: model-agnostic LLM boundary
│   └── client.py        # LLMClient (ABC) + OllamaClient
│
├── <feature>/           # one package per feature (commits, summarization, ...)
│   ├── models.py        # this feature's domain value objects / DTOs
│   ├── service.py       # this feature's business logic (classes)
│   ├── router.py        # FastAPI routes for this feature (thin) — where applicable
│   └── client.py        # external boundary the feature owns — where applicable
│
scripts/                 # composition-root entrypoints for offline runs (spike, eval)
evals/                   # eval fixtures, references, outputs
```

A feature adds a package under `src/`; it does not scatter its models into a shared root `models/`. Infra modules (`core/`, `llm/`) are the only shared homes, and they hold cross-cutting concerns, not feature logic.

## Dependency Rules

- Features depend on infra modules (`core/`, `llm/`), never the reverse.
- A feature never imports another feature's internal files. If feature B needs feature A's capability, it depends on A's public class/interface, injected via constructor.
- Concrete implementations are chosen **only** at the composition root (`main.py` / `scripts/*`). Feature and service classes receive abstractions (e.g. `LLMClient`), never construct concretes themselves.

- ✅ `summarization` depends on the abstract `LLMClient` from `llm/`; the composition root injects `OllamaClient`
- ✅ `core.Settings` is read at the composition root and passed down; features do not read env directly
- ❌ A service instantiating its own `OllamaClient` (couples business logic to a concrete backend)
- ❌ A root-level `models/` collecting every feature's types (breaks feature ownership)
- ❌ Importing another feature's `service.py` internals instead of depending on its public class

## Layer / Feature Communication

Within a feature the standard flow applies:

```
Router (thin, HTTP concerns, validates DTOs)  →  Service (business logic)  →  Client / Repository (external)
```

Between features and infra — only through injected public objects:

```python
# summarization/service.py — depends on an abstraction, not a backend
class Summarizer:
    def __init__(self, llm: LLMClient, prompt: PromptBuilder) -> None:
        self._llm = llm
        self._prompt = prompt

    async def summarize(self, context: CommitContext, lang: str = "ru") -> str:
        return await self._llm.generate(self._prompt.build(context, lang))

# scripts/summarize_range.py — the composition root wires concretes
settings = get_settings()
summarizer = Summarizer(
    OllamaClient(settings.ollama_url, settings.ollama_model, settings.ollama_api_key),
    PromptBuilder(),
)
```

## Key Principles

1. **Feature = boundary.** One package per feature; it owns its models and services. Cross-cutting concerns live in `core/` and infra modules only.
2. **Services own business logic; routers/CLIs are thin.** Entry points validate/parse and delegate — no logic in a router or a script beyond wiring.
3. **Dependency injection via constructor.** Classes receive their collaborators; they never `new` up a concrete external client. Wiring happens only at the composition root.
4. **Abstractions at every external seam.** The LLM boundary (`LLMClient`) is abstract so the backend (Ollama today, larger/hosted later) swaps without touching feature code. Introduce an ABC when a real second implementation is imminent — not speculatively.
5. **Config is injected, not read ad hoc.** `Settings` is read once via `get_settings()` at the root and passed down; concrete clients take primitives, staying unaware of the config layer.
6. **Encapsulation.** A feature exposes classes, not internals. Prompt text, git-command details, HTTP specifics stay inside the class that owns them.

## Anti-Patterns

- ❌ **Layer-first dumping** — a root `models/`, `services/`, `utils/` holding every feature's code. Organize by feature instead.
- ❌ **Concrete instantiation in business logic** — a service building its own `OllamaClient`/`httpx` client. Inject the abstraction; wire at the root.
- ❌ **God service** — one class spanning unrelated features. Split per feature.
- ❌ **Env read inside features** — calling `os.getenv` deep in a service. Read `Settings` at the root, inject it.
- ❌ **Reaching into another feature** — importing its `service.py`/`models.py` internals rather than depending on its public class.
- ❌ **Logic in entry points** — parsing/collecting/summarizing inside a router or a `scripts/*` file. Entry points only assemble and delegate.
- ❌ **Hardcoded secrets or host details** — Ollama URL, SSH host/key, tokens. Always from env via `Settings`; never in committed code.

## Features (roadmap-prune v2)

| Feature | Hashes |
|---------|--------|
| **Change summarization & the model boundary** | |
| Read a repo's commit history | 8b2a8a8 38f9eb3 d47f195 |
| Summarize a commit range into release notes | ce763e4 4dec969 |
| Generate and embed text through a model-agnostic boundary | 2c020c0 a2a7b56 1ef0f26 |
| **Ingestion & authorization** | |
| Receive signed GitHub App push webhooks | e417618 fd454ae |
| Serve only allowlisted organizations | 177bcdc |
| Track which repositories the installation reaches | ae8cd04 |
| **Repo mirror** | |
| Mirror a served repo under GitHub App credentials | b7e7a9b 2432a1b |
| **Semantic memory** | |
| Store and search project knowledge by meaning | 9a12031 e9f89b2 |
| Index a project's curated artifacts | 6beac1c d551b5b |
| Keep a project's knowledge fresh from its canonical ref | 0956f17 |
| Understand a code-only project at feature level | e0f6435 84a84ac 69cbb37 67c869d |
| **Episodic memory** | |
| Append and query a project's change history | 10df41c c5c4a5f |
| Resolve a push to its linked change | ec5eecd c7e3e00 |
| Record every served push as an episode | b158c93 |
| Backfill a repo's history into episodic memory | e415d23 1e632a8 |
| **Project graph** | |
| Register directed cross-project edges | 319facb b88b7c9 |
| Seed member edges from a coordination root | cd510dd |
| **Reasoning & narration** | |
| Answer a question from both memories | 27e3575 0740a80 |
| Reach neighbouring projects in an answer | d7702e5 |
| Narrate a change as feature-level prose | b8a7b56 |
| Produce a note per requested language | 5283570 dc97def |
| **Delivery & routing** | |
| Route a push by branch role | e984bb3 |
| Post a note to Telegram | 7ff56db 1167e7f |
| **Reporting** | |
| Compose a report from configured sections | ca15519 4573aa6 |
| Deliver scheduled daily and weekly reports | a16824f |
| Build a report in each channel's language | af57a36 |
| **Releases & the changelog protocol** | |
| Assign a version from the repo's own tags | 0783684 |
| Report the window since the last deploy | 366e882 e3972ec |
| Cut a GitHub release with a version header | 1bb7597 |
| Publish a changelog entry to a mapped app | 99008e3 2dafad8 |
| **Verification** | |
| Run producer quality against fixed eval cases | 313f82b c2b33ed f88d3da 0cef3a6 |
| **Internal** | |
| Roadmap drop history | 6b1b1de |
