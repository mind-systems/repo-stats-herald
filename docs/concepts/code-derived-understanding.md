# Code-Derived Understanding (concept)

A forward-looking design. Today Herald builds its knowledge model from a project's
curated artifacts — the human-written roadmap, architecture, and docs (see
[understanding.md](../behavior/understanding.md)). This concept describes how a project
that has **no such artifacts** — only code — is still understood at the level of
features, not classes. This mode ships: the source strategy that selects a
code-only project's files and the distiller that turns them into feature-level
prose both exist, and this document is the contract they answer to.

## The problem it answers

Every repository shares one artifact: **its code**. It is tempting to conclude that
the knowledge store should therefore be built on code. That conclusion is wrong in its
naive form, and the reason is the whole point of this concept.

Embedding raw code into the store reproduces, at the retrieval layer, the exact
failure Herald exists to avoid:

- Code chunks embed by lexical and structural similarity, so retrieval surfaces
  *similar code*, not a *related feature*.
- A feature is cross-cutting — it lives across many files; a chunk is one file or
  region. The unit of retrieval is wrong for the unit of meaning.
- An LLM handed code describes mechanism — classes, methods, call chains — not
  delivered value. Narration collapses back to "what the classes do."

So "code as the base of the RAG" cannot mean "embed code." It means something else.

## Two layers that must not be conflated

Herald's current indexer is one step: `read → chunk → embed`. That works only because
its input is already the right thing. Separate the two layers it hides:

- **The meaning layer** — text that describes the project in terms of *features and
  direction*. This is what the store must always hold.
- **The retrieval layer** — what physically lives in the store and is searched.

The store is always fed the meaning layer. The only question is where that layer
**comes from**:

- A project **with a harness** (roadmap, architecture, docs): a human already wrote
  the meaning layer. Herald indexes it directly — cheap, high-fidelity. Unchanged.
- A project **with only code**: the meaning layer does not exist yet. Herald must
  **produce** it — run the code through the LLM *once, at index time*, to derive
  feature-level descriptions, and embed **those**.

Code never enters the store raw. Between the raw source and the store sits a
**distillation stage** — `code → LLM → feature descriptions → embed` — that the
current tasks do not have: their indexer has no LLM in the loop.

## Distillation happens once, not per push

The crucial property: teaching the model to see features rather than classes is done
**once per snapshot**, not on every push at narration time. It is the same work a
human does by hand when authoring a roadmap or architecture doc — automated, and with
a human able to review the result before it becomes ground truth. Narration itself
never reasons from raw classes; it always reasons from a settled meaning layer.

## What counts as a feature — the distillation rubric

The class-vs-feature risk is held down by a discriminator, not by hoping the model
generalizes. The distillation asks, of each candidate unit:

> Could you write an e2e test for this that didn't exist before?

Yes — it is a feature: any verifiable interaction counts (user→system,
system→system, system→external service, or an internal subsystem with its own
behaviour contract). No — it is internal (a refactor, a cleanup, plumbing) and stays
out of the inventory. On top of the discriminator, the naming discipline:

- a feature is named in 2–5 words from the operator's perspective — what the system
  can do, never how it is built;
- prefer fewer, larger features — a cross-cutting capability spanning many files is
  one entry, not one per module;
- module and directory names never become feature names.

This is the same rubric that curates the `## Features` table an ai-factory harness
keeps in its `ARCHITECTURE.md` — proven on human-authored roadmaps before any
distillation reuses it — so the bootstrap's output speaks the same language as the
artifacts a harnessed project already feeds the store.

## Three ways to serve a code-only project

- **Standing code profile** — code is distilled into the store on every snapshot.
  Most powerful, but the class-vs-feature quality risk recurs on every run; each pass
  is a fresh gamble on distillation quality.
- **Accept shallow** — fall back to the commits-only floor: commit-level narration,
  no feature model. Honest, but a code-only project stays half-blind.
- **One-time bootstrap** *(recommended)* — the LLM distills the code into a
  feature inventory / architecture document **once**; a human corrects it; it lands in
  the repo as an ordinary artifact. From then on the project is an ordinary
  artifact-bearing project, and the entire downstream pipeline is identical.

The bootstrap is the recommended shape because it removes the standing risk: the model
is never asked to narrate features from classes at runtime. The one-time, reviewable
`code → features` distillation yields the same text layer a harnessed project already
has, and nothing downstream changes. "The common denominator is code" resolves not to
*"we always narrate from code"* but to *"the meaning layer can always be bootstrapped
from code when it is missing."*

## Where it fits

This is the **derivation engine's** other mode. The engine either **distills from
artifacts** (a human did the work) or **derives from code** (Herald does the work, a
human reviews it); the source-strategy profile
([source-strategy-profiles.md](source-strategy-profiles.md)) selects the mode, and the
two engines over the event stream (see
[architecture.md](../architecture.md#the-two-engines-over-the-event-stream)) are
unchanged above it. The distillation stage is the one new seam the code mode adds.
Code is one end of a richness spectrum the derivation mode follows over a repo's
timeline — see [derivation modes over a repo's timeline](derivation-modes.md).

## Non-goals and when to build

- Today only artifact-fed understanding and the commits-only floor are needed. The
  distillation stage and any code-derivation profile land when a **code-only project
  must be served** — the "extract after the second shape" discipline.
- Bootstrap output is a human-reviewed artifact by design; automated distillation is
  never trusted as ground truth without that review.
- The mirror stays generic — the distillation stage reads code from the complete local
  mirror; it never changes how repos are fetched.
