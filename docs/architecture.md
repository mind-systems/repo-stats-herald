# Architecture

This document describes the shape of Herald — how a stream of pushes becomes an understanding of each project and a narration of its progress. The topic docs under `docs/spec/` describe *what* each part does; this one describes *how the parts fit* and the seams between them. The code-organization pattern — feature-modular packages, dependency injection, the composition root — lives in `.ai-factory/ARCHITECTURE.md`; this is the domain architecture above it.

## The unit of understanding: intent → change → outcome

Herald's data is not a flat log of commits. Its core unit is a **linked change**: a change resolved to the intent it serves and the outcome it produces.

- **Intent** — what the project set out to do: a roadmap task, a direction stated in a design doc.
- **Change** — what actually happened: the commits in a push and the artifacts they touched.
- **Outcome** — the resulting shift: a feature advancing, a task moving from open to done.

Narration reasons over these links. A commit on its own is a diff; the same commit resolved to the task it completes and the feature it advances is *progress*. The architecture exists to hold that link and reason over it — the intent and outcome around a change, not the change alone. Each such linked change is one entry in Herald's episodic memory (see [the two engines](#the-two-engines-over-the-event-stream)); their accumulation over time *is* the project's evolution.

## Seams

Herald is a set of boundaries, each holding one concern behind an abstraction so its backing can change without disturbing the rest — the same discipline the LLM boundary follows for the model backend, applied throughout.

| Seam | Holds | What it keeps swappable |
|------|-------|-------------------------|
| **Ingest** | turning an incoming push into an event on the project's stream | the event source and its wire shape |
| **Source strategy** | the per-project selection of which files define a project and how to read them | the harness a project uses |
| **Knowledge model** | the standing, per-project understanding of what the project *is now* — features, direction, state | how understanding is derived and kept |
| **Knowledge store** | the persistence and retrieval behind the current model — the semantic memory | the storage engine (a vector store today) |
| **Episodic store** | the append-only log of *how* the project changed — each linked change retained over time, so removed work stays recoverable | the storage engine behind the history |
| **Reference set** | the curated ground truth Herald measures against — declared relationships, user-authored references | where truth comes from, apart from what is inferred |
| **Reasoner** | turning the two memories and a change — or a direct question — into human prose; narration is one mode | the model and the phrasing |
| **Delivery** | routing the reasoner's output to the channels a branch activates | the channels and their formats |

Each seam is an interface; the concrete behind it is wired only at the composition root. The store is a commodity chosen for the job and swappable; the LLM is swappable; the ingest source is swappable. The domain layer — the model, the linked-change reasoning, the narrator — is Herald's own and depends on no single backend.

## The two engines over the event stream

Herald does not read a project's current files and summarize them. It replays the project's **event stream** — its pushes and their commits, in order — and derives what it knows from that replay. A per-project **source strategy** (which files define the project, how to read them) tells the engines how to read the stream: a harnessed project exposes a curated source set (roadmap, specs, docs) while the artifacts an orchestrator writes in passing and the code stay out; a project with no harness falls back to the source every project has — its commits and their messages.

Two engines sit over the stream.

**The derivation engine** replays the stream into understanding. On each event it resolves the change to its linked chain — intent → change → outcome — and updates two memories:

- **Semantic memory** — the [knowledge store](spec/understanding.md#a-per-project-retrieval-store): the standing model of what the project *is now*, its features, direction, and built-vs-remaining state. It is a current projection of the stream, re-derivable at any time.
- **Episodic memory** — the append-only log of *how* the project changed: each linked change retained in order, so a feature that once existed and was later removed is still recoverable. This is the project's history, not its present.

**The reasoner** reads both memories and turns a query into prose. It answers from what the project is now (semantic) and how it got there (episodic): the reports and release notes Herald broadcasts are one mode; a direct question about the project's past — what a feature was, when it changed, why it was dropped — is another. The reasoner sits behind a model boundary, so a small local model and a larger hosted one are the same seam with a different backend; the memory it reasons over does not change when the model does.

The stream is the source of truth; semantic memory is its current projection; episodic memory is its history. The derivation engine writes both; the reasoner reads both; both consult the source strategy. Retrieval is the access lens over either memory, not a property of one.

Today one source-strategy profile ships (the ai-factory default); making the strategy a plugin system of per-project profiles is a forward-looking concept — [source-strategy profiles](concepts/source-strategy-profiles.md). Where a project exposes no curated artifacts, the derivation engine can derive understanding from code itself, distilled once and reviewed — [code-derived understanding](concepts/code-derived-understanding.md).

## The flow

A single push moves through the seams in order:

1. **Ingest** verifies the push and turns it into updates — the changed artifacts, the commits, the branch (see [ingestion](spec/ingestion.md)).
2. The **derivation engine** absorbs the event: the affected source files (per the source strategy) are re-derived into the **knowledge store** (semantic memory), and the resolved change is appended to the **episodic store** (see [knowledge-model](spec/understanding.md#per-project-knowledge-model)).
3. The change is **resolved to its linked chain** — the intent it serves and the outcome it produces — drawing the intent from the roadmap and design docs the model holds (see [narration](spec/narration.md)).
4. Where the change touches another project, the **project graph** and retrieval surface the neighbors, and the chain extends across projects (see [project-graph](spec/understanding.md#project-graph), [cross-project narration](spec/narration.md#cross-project-narration)).
5. The **reasoner** turns the resolved chain, its retrieved context from both memories, and the reference set into prose at the level of features and direction — the narration Herald broadcasts, one mode of what it can answer.
6. **Delivery** routes the prose to the channels the branch role activates (see [delivery](spec/delivery.md)).

## Principles

- **A seam per external concern.** The store, the LLM, the ingest source, and the reference set each sit behind an interface. A backend is a choice held at the edge, never threaded through the domain code.
- **Commodity below, domain above.** The mechanical layers — vector math, embeddings, storage — are commodities taken off the shelf. The layer that resolves a change to its intent and outcome and narrates it is Herald's own.
- **Understanding is standing, not recomputed.** The model persists and updates incrementally on each push; a push is read against what Herald already knows, not against a fresh read of the whole project.
- **Reason over links.** The architecture earns its keep by holding the connection between a change, its intent, and its outcome. Everything above the store exists to keep that link and narrate it.
