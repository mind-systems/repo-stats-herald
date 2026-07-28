# Source-Strategy Profiles (concept)

A forward-looking design. Today Herald ships two concrete source strategies — the default ai-factory profile and a code-only profile — each wired at a composition root rather than resolved through a registry (see [architecture.md](../architecture.md) and [understanding.md](../behavior/understanding.md)). This concept describes how those strategies become a **plugin system of profiles** when a third project shape needs its own. It is written as the target contract; it is not built, and nothing here is a commitment to build it before a third project shape makes it earn its place.

## Why

A project's source strategy — which files define it and how to read them — is the thing that varies most between projects. Herald meets several shapes in the wild:

- an **ai-factory** project: a layered governing spec — `ROADMAP.md`, `docs/**`, `CLAUDE.md`, `ARCHITECTURE.md` — with plans and plan reviews written in passing that are not part of its identity;
- a **README-centric** project: one large `README.md` plus a small `ARCHITECTURE.md`, with translations and assets that are noise;
- a **manifesto / Claude-harness** project: a `CLAUDE.md` of principles plus scattered engineering docs, with a roadmap but no governing spec.

And every project, harness or not, has the universal floor: **its commits and their messages**.

Holding these in one hardcoded filter couples Herald's core to specific project conventions. A profile makes each shape a swappable unit, so a new shape is added without touching the engines.

## What a profile is

A **profile** is a named source strategy — a plugin that answers, for one project shape, three questions:

- **Selection** — which paths are sources (`selects(path) -> bool`), and which are noise (orchestrator plans and reviews, code, translations, assets).
- **Read policy** — how a selected file becomes knowledge: the chunking/parse rule (whole Markdown sections for docs; a commit-message digest for the commits-only floor).
- **Change interpretation** — how the derivation engine reads *what moved* for this shape (`[ ] → [x]` roadmap transitions for ai-factory; PR titles for README-centric; commit messages for the floor).

Both engines consult the profile: the derivation engine for the snapshot it indexes and the change it logs, the reasoner for how it narrates (see [architecture.md](../architecture.md#the-two-engines-over-the-event-stream)).

## The built-in profiles

Herald ships a small set, and always the floor:

| Profile | Sources | Change interpretation |
|---------|---------|-----------------------|
| **ai-factory** | `CLAUDE.md`, `ARCHITECTURE.md`, `ROADMAP.md`, `AGENTS.md`, `docs/**` | roadmap `[ ] → [x]` transitions, anchored to spec/design docs |
| **readme-centric** | `README.md`, `ARCHITECTURE.md`, top-level docs | PR titles and bodies; sections of the README |
| **claude-harness** | `CLAUDE.md`, `ROADMAP.md`, `docs/**` | roadmap state plus commit messages |
| **commits-only** (floor) | the commits and their messages | the commits themselves |

The floor always applies where no richer profile fits, so every served repo is narratable at some depth — the "depth follows what a project exposes" principle.

## Resolving a profile per repo

A repo gets a profile two ways, override-first:

- **Auto-detect** — Herald reads the mirror's shape: an `.ai-factory/` directory → ai-factory; a dominant `README.md` with an `ARCHITECTURE.md` and no `.ai-factory/` → readme-centric; a `CLAUDE.md` without a governing spec → claude-harness; nothing recognized → commits-only.
- **Configured override** — an operator pins a repo (or an org's default) to a named profile in the configuration registry, winning over auto-detect.

Detection is a best-effort classifier; the override is the escape hatch for when it guesses wrong.

## Extensibility

Profiles are a registry of named strategies behind one interface. A new project shape is added by registering a new profile — built-in, or discovered as a plugin (an entry point or a drop-in module) — without touching the engines or the mirror. The interface (selection, read policy, change interpretation) is the stable contract each profile implements.

## Non-goals and when to build

- The **ai-factory** default, the **code-only** profile, and the **commits-only** floor cover every shape served today, each chosen at a composition root. The registry, auto-detection, and additional profiles land when a **third real project shape** must be served, or sooner if profile selection has to be resolved at runtime rather than wired.
- Profile configuration is operator config (the registry), part of the multi-tenant configuration evolution (see [configuration.md](../behavior/configuration.md)) — not a UI concern here.
- The mirror stays generic: a profile decides only what is read from the complete local mirror, never how repos are fetched.
