# Derivation Modes Over a Repo's Timeline (concept)

A forward-looking design. It refines how the derivation engine (see
[architecture.md](../architecture.md#the-two-engines-over-the-event-stream)) chooses
its source as it replays a repo's history — extending
[code-derived understanding](code-derived-understanding.md) (the no-artifacts end) and
[source-strategy profiles](source-strategy-profiles.md) (the selection mechanism). It
is not built; it is the target contract for when history is replayed into episodic
memory and when a no- or poor-harness project must be served.

## Derivation mode is not fixed per repo — it follows harness richness at each point in time

A repo is not "an ai-factory repo" or "a code-only repo" for all time. Its harness —
the curated artifacts that make it legible — *appears and matures* over its history.
Every ai-factory repo predates its own `.ai-factory/`; `tradeoxy_broker` grew its docs
gradually. So the derivation engine's source is a function of **how rich the harness is
at the point in the timeline being read**, not a label fixed to the repo.

Richness is a spectrum, not a switch:

| Harness richness | Semantic source | Episodic intent-anchoring |
|---|---|---|
| **None** — code only | distilled from code (a reviewed bootstrap) | the commit message alone |
| **Poor** — a README, thin docs, no roadmap/specs | artifacts where they cover; code distillation fills the gaps | commit messages / PR titles — inferred, weak |
| **Rich** — roadmap + specs + docs | the artifacts alone; code is not read | roadmap `[ ] → [x]` transitions — curated, strong |

The change-and-outcome signal — the commits and their diffs — is always present
regardless of richness; it is the floor. What richness moves is (a) whether the
*semantic* snapshot is read from code or from artifacts, and (b) how strongly
*episodic* intent anchors to a curated statement of purpose rather than an inferred
one.

## The taxonomy, honestly: three trajectories on the spectrum, not four modes

Four modes suggest themselves; they resolve to three trajectories along the richness
axis, plus one non-case:

1. **Never harnessed** — code-only across the whole timeline; code-derived throughout.
2. **Always harnessed** — artifact-derived throughout. Rare; most repos predate their
   harness.
3. **Acquired a harness** — code-derived early, artifact-derived later: the repo
   *climbs the richness spectrum* over time. The common, gradual case.
4. **Lost its harness** — a non-case as a trajectory: real repos do not delete their
   roadmap and docs and keep developing. And the architecture handles even the
   accidental version for free — if a doc is removed, *semantic* memory simply stops
   seeing it going forward, while *episodic* memory retains it (append-only is the
   whole point). A "lost" harness needs no special mode; the history of when it existed
   is never lost.

The fourth mode's real content is not "lost" but "**stayed poor**": a repo that
acquires a harness but a thin one — some docs, no roadmap, no specs — and plateaus
there. That is not a fourth trajectory; it is trajectory 3 stopping partway up the
richness spectrum, and it is exactly why richness is a spectrum and not a binary. A
poor harness is not enough to stop reading code: where the docs say little and there
are no tasks, code distillation still fills the semantic snapshot and episodic intent
stays inferred. A rich harness earns the opposite — everything is already described in
the docs and the tasks, so there is nothing to squeeze from code.

## The mechanism: the profile is evaluated per historical tree

Because richness is per-point-in-time, replaying history applies the source strategy to
the **tree state at each commit**, not once to the current `HEAD`:

- The semantic memory syncs to `HEAD` — "what the project is now" — correctly
  evaluated once.
- The episodic memory, replaying the stream, evaluates the profile against each
  historical tree: early entries yield commits-only linked changes, later ones yield
  roadmap-anchored ones.
- The code-derivation mode fills the early stretch where only code existed.

So along a single repo's timeline, **code-derived and artifact-derived entries
coexist**: earlier from code, later from the harness, with the crossover wherever the
harness became rich enough. The evolution log captures not just the project's features
changing, but the project *becoming legible* — growing its own self-documentation.

## Crossed with the two memories

The two axes — richness and memory type — compose. Richness sets, per point in time:

- for **semantic memory** (what the project is now): the *source* — code ↔ artifacts;
- for **episodic memory** (how it changed): the *intent-anchoring strength* —
  inferred-from-commits ↔ anchored-to-roadmap-tasks.

The episodic *change* and *outcome* halves come from code either way; only the *intent*
half strengthens as the harness richens. So a repo's episodic log naturally reads as
weak-intent early and strong-intent late — and that gradient is itself a true signal of
when the project started stating its own purpose.

## When to build

- The **commits-only floor** covers early history with no work, so the full profile
  plugin is not a prerequisite to start replaying — the profile and code-derivation
  engage progressively, where they earn their place.
- Per-historical-tree evaluation and the code/artifact crossover are decomposition
  concerns for the episodic-memory and code-derived phases (16 and 24 in the reimagined
  roadmap), not for the semantic snapshot (which reads `HEAD`).
- Nothing here is built until history is actually replayed into episodic memory and a
  poor- or no-harness repo must be served.
