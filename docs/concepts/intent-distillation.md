# Intent Distillation (concept)

A forward-looking design. Today the intent half of an episodic entry anchors to a
curated statement where one exists — a roadmap task the change completes — and falls
back to the raw commit message where none does (see
[derivation modes](derivation-modes.md)). This concept inserts a middle rung: where no
human-written anchor exists, the change itself is distilled **once, at ingest** into a
task-spec-shaped statement of intent — what the change was tasked to accomplish — and
that statement, marked as inferred, becomes the entry's intent. It is written as the
target contract; it is not built, and nothing here commits to building it before a
weak-intent history must actually be narrated.

## The problem it answers

A commit that completes no roadmap task gets its commit message as intent. Messages
vary wildly in care — "fix", "wip", a one-liner about mechanism — so the weak-intent
stretches of the episodic log are only as articulate as whatever the author typed. A
question over such a stretch — *why was this changed?* — is answered from that message
alone, even though the diff itself carries enough signal to state, in feature terms,
what the change set out to do. Nobody wrote that statement down; Herald can.

## What distillation produces

A **spec-shaped intent statement**: the assignment the change fulfills, phrased as
delivered value — the task spec a human would have written before making this change. It
names what the change enables or corrects, never how — no classes, methods, or call
chains; the mechanism ban of
[code-derived understanding](code-derived-understanding.md) applies in full. One
statement per linked change, produced from the diff and the message together, stored
in the episodic entry with its provenance.

The statement's shape mirrors a curated roadmap contract line: one bounded paragraph —
the problem the change answers, then what it delivers — so distilled and curated
intents read in the same register and an episodic query returns a uniform log, not two
prose styles split by provenance.

## The anchoring ladder

Distillation slots into the existing gradient rather than replacing it:

| Rung | Intent source | Nature |
|------|---------------|--------|
| 1 | roadmap `[ ] → [x]` transition + its task spec | curated, strong |
| 2 | PR title and body | human-stated |
| 3 | **distilled intent** — LLM-inferred from diff + message | inferred, marked |
| 4 | raw commit message | the floor |

Distillation engages only below the human rungs and never overrides a curated anchor —
a change that completes a roadmap task keeps the task as its intent, whatever the LLM
might have guessed. Each entry records which rung its intent came from, so the
reasoner can weight and phrase accordingly: a curated intent is stated as fact, a
distilled one is hedged as read from the change.

## Why this is not the rejected per-push code distillation

[Code-derived understanding](code-derived-understanding.md) rejects standing per-push
distillation for the **semantic** store: narrating what the project *is* from raw
classes, re-gambled on every run. This concept is **episodic** and shaped differently
on every axis that made that a gamble:

- the unit is one bounded diff, not a whole codebase snapshot;
- the output is one intent statement, appended once and never re-derived;
- it feeds the history, not the standing model — the semantic store still holds only
  curated (or bootstrap-reviewed) artifacts.

The quality risk is bounded to match: a bad distilled intent misstates one log entry,
visibly marked as inferred — it never becomes ground truth about what the project is.

## Reverts distill too

A revert's distilled intent names what it withdraws. Retrieval over the episodic log
surfaces the original entry, so the pair reads as add-then-withdraw, and a narration
whose range covers both nets them out instead of announcing a feature that never
shipped.

## Retrieval over distilled intents

Episodic entries — distilled intents included — are embedded like any memory content;
retrieval is the access lens over either memory (see
[architecture.md](../architecture.md#the-two-engines-over-the-event-stream)). This is
what makes "search the project's history commit by commit" work without raw code ever
entering a store: the searchable unit is the intent statement, not the diff behind it.

## Where it fits

Distillation runs inside the **derivation engine**, at the step that resolves a change
to its linked chain; the source-strategy profile's change interpretation
([source-strategy-profiles.md](source-strategy-profiles.md)) decides when it engages —
exactly where the profile would otherwise fall through to the commit-message floor. It
adds no new external seam: the statement is produced through the existing LLM
boundary. During a history replay (see [replay](../behavior/replay.md)) it applies per
historical tree, so the early, unharnessed stretch of a timeline gets distilled
intents instead of bare messages — the weak-intent gradient of
[derivation modes](derivation-modes.md) is lifted, not merely recorded.

## Non-goals and when to build

- Distilled intent never feeds the semantic store and never displaces a curated
  anchor; its provenance mark is permanent.
- Cost is one LLM call per unanchored change. A replay over a long weak-intent history
  multiplies that; whether to distill the whole stretch, a sampled part, or on-demand
  at question time is a build-time decision, not fixed here.
- Nothing is built until episodic memory exists and a poor-harness repo — or a replay
  over a weak-intent history — must actually be served.
