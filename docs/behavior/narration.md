# Narration

How Herald turns its understanding of a project into human prose at the level of features and direction. The reasoner reads a change against the two memories — the standing model of what the project is now (semantic) and the log of how it changed (episodic) — and the project graph, and phrases what it means. Narration is one mode of the reasoner; the same machinery answers a direct question about a project (see [architecture](../architecture.md#the-two-engines-over-the-event-stream)).

## Feature-level, not a commit log

Narration speaks in features and direction, not diffs. A change is first resolved to its **linked chain** — the intent it serves (the roadmap tasks it completes) and the change itself (its commits) — and the narration leads with the completed tasks, the curated statements of delivered value, with the commits as supporting detail. Where a change completes no roadmap task, the narration falls back to a commit-level digest of what is significant.

The reasoner phrases this by reading the change against the two memories: the semantic model gives a feature its current meaning, the episodic log gives it history, and retrieval surfaces whatever else in the organization relates to it (see [Cross-project narration](#cross-project-narration)). The output is prose about what moved and what it unblocks — never a raw list of commits.

## What feeds a narration

Quality comes from what is fed in more than from a bigger model, so a narration is grounded in the richest signal the change offers:

- **The resolved change** — the completed roadmap tasks (the anchor) and the commits behind them. The task anchor lifts a narration from a list of edits to a statement of what shipped, in wording a human already curated, and filters bookkeeping for free: purely technical commits (roadmap edits, docs churn) fall away because the anchor is the completed task, not every commit.
- **Pull requests** — where the change carries them, PR titles and bodies add the intent a diff omits.
- **Retrieved memory** — semantic (what the project is now) and episodic (how it got here), retrieved against the change so the narration is framed by the project's standing model rather than the diff alone.
- **The project graph and neighbors** — related projects surfaced by retrieval and by declared edges, so a change is framed in ecosystem terms.

A repository whose roadmap is in a recognized format gets the task anchor; one without is narrated from its commits and the retrieved model. The base capability never assumes any one project's conventions.

## Range

Narration always works over a range of the project's history; what sets the range is the trigger, not the branch:

- a **report** narrates a time window — a day or a week (see [Reports](#reports));
- a **release note** narrates the accumulation since the last deploy to that environment — everything that landed since the previous release, condensed to what matters (see [delivery.md](delivery.md#versioning)).

A narration is built from the history over its range, never from a single push in isolation.

## Languages of generation

A narration is generated in every language its delivery's active channels require, and each language is a separate generation. The set of required languages is the union across the channels active for that delivery:

- a report to an organization whose Telegram channel is Russian needs only Russian;
- a release to a repository with no integrated app needs Russian for Telegram and English for the GitHub release — two single-language channels, one generation each;
- a release to a repository whose app declares `["ru", "en"]` needs the same Russian and English, now consumed by the app store as well, while Telegram still takes only Russian and the GitHub release only English.

Each fixed channel — Telegram and the GitHub release — delivers in exactly one language; only the app changelog store carries several. Generating the union means a language produced once feeds every channel that asks for it, not that any fixed channel becomes multilingual. Which channel consumes which language is a delivery concern — see [delivery.md](delivery.md). Narration's responsibility ends at producing each required language.

*How* those languages are produced sits behind a swappable localization seam: either each is generated natively, or a single canonical language is generated and the rest are translated through a translation seam. A smaller model reasons best in one language and translates from it; a stronger one can generate each natively. The strategy moves with the model without touching the callers, which ask only for a note per required language.

## The LLM boundary

The LLM sits behind a model-agnostic boundary: business logic depends on an abstract client that exposes a single "generate text from a prompt" operation and names no Ollama concept. The concrete backend — a local Ollama model today — is wired in only at the composition root and swaps for a larger or hosted model without touching the narration logic. Timeouts and transport errors surface as failures rather than a silently empty summary.

## Cross-project narration

A change to one project rarely stands alone: it advances a feature another project depends on. Cross-project narration frames a change in ecosystem terms — what it moves, and what that unblocks elsewhere.

### Neighbors surface through retrieval

Which projects a change touches is answered by retrieval. The change is queried against the org-wide knowledge (see [understanding.md](understanding.md#per-project-knowledge-model)), and retrieval surfaces the related context by semantic similarity — from the changed project and from others. Whatever relates to the change comes back in the result, so Herald reads its neighbors off the query and narrates what actually surfaced.

### The project graph is the precise complement

A relationship a project declares in its own docs — a proto it owns, a consumer it names — is already in the knowledge store, so it surfaces through retrieval. The [project graph](understanding.md#project-graph) carries only the relationships retrieval cannot infer: couplings real in the code but declared nowhere. Herald follows those edges in addition to what it retrieves.

### What it produces

Cross-project narration names the feature that advanced and the project it belongs to, then the work it unblocks in the projects that depend on it — direction and dependency, at the feature level. Where retrieval surfaces no related project and the graph has no edge from the change, the note stays single-project.

## Reports

A served push writes memory but is not reported on its own. Herald speaks in **reports** — daily, weekly, and (on release, see [delivery.md](delivery.md)) per deploy. A report is not a fixed shape: it is an ordered composition of **content sections** over a time window, produced as one text and delivered like any note.

- **Sections** are the units of meaning, each self-contained: a **summary** (holistic "what moved", the same shape a release note carries), a **per-branch** breakdown (who did what, branch by branch), and more as they are needed. Each is its own component, not a mode of one function.
- **A report** composes an ordered set of sections over a window: a daily report might be a summary plus a per-branch breakdown of the day; the weekly, a summary of the week's arc. Which sections compose which report — over which window and cadence — is configuration, so a new report, or a new block on an existing one, is a setting, not a rewrite.
- **Feature framing and ecosystem view** carry through every section that narrates: progress is measured against the [knowledge model](understanding.md#per-project-knowledge-model) and roadmap state, and cross-project unblocks come from the [project graph](understanding.md#project-graph) and retrieval.

The same engine expresses the day's report, the week's, and the release note — a summary section on the release trigger (see [delivery.md](delivery.md#versioning)). A report is delivered through the routing layer like any note — Telegram in Russian by default, at the report's cadence.

## Quality is measured, not eyeballed

Summary quality is checked against fixed cases rather than judged ad hoc. A case set pins `{repository, range, language}` inputs against user-authored reference notes, and the harness writes one output per case under stable filenames for diffing against the references. Any change to the prompt or the model is run through the harness before it is trusted, and approved notes fold back into the case set and the few-shot prompt so quality compounds over time.
