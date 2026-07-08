# Replay

Herald usually meets a project mid-life. Replay is how it earns the history it was not
there for: Herald walks the repository's past through the same engines that serve live
pushes, in simulated time, and delivers the reports it would have delivered had it
served the project from its first commit. The Telegram channel that receives them ends
up holding the project's whole development story, readable start to finish — and the
run doubles as end-to-end acceptance of narration quality over a real history.

## Simulated time

Replay drives the [derivation engine](../architecture.md#the-two-engines-over-the-event-stream)
over the repository's commit history, oldest first, exactly as live ingestion would —
the same stream, arriving from the past instead of from a webhook. At any point of the
run, memory holds what Herald would have known on that date:

- **semantic memory** tracks the tree at the replay cursor — "what the project is now"
  as of that historical moment, not as of `HEAD`;
- **episodic entries** carry the historical commit dates — history is never
  collapsed into the run date;
- the **source strategy is evaluated against each historical tree**, so early
  commits-only history and later roadmap-anchored history both land as they were at
  the time (see [derivation modes](../concepts/derivation-modes.md)).

When the cursor reaches a window boundary, the reasoner narrates from the memory state
at the cursor — the same report a live deployment would have produced that day. Then
the cursor moves on.

## Active-day windows

A live report fires on the calendar; a replayed report fires on **activity**. Replay
counts non-empty days — days with at least one commit in the repository — and cuts a
report every N of them. N is a launch parameter: 15 approximates a two-week sprint, 30
a monthly digest. Calendar gaps are skipped silently — a dormant quarter produces no
empty reports, and the chronicle reads at the density the project actually had.

The report itself is the standard composition of sections over its window (see
[reports](narration.md#reports)): what moved and what it unblocks, the per-branch
breakdown — which branches appeared, who worked where — and the remaining direction.
Its header carries the window's historical dates, never the run date.

## Tag milestones

Where the history carries version tags, replay treats each as the release milestone it
was: it cuts a release-style note accumulating everything since the previous tag — the
same shape as a live [release note](delivery.md#versioning) — and delivers it, with
its version header, in order between the periodic reports. One replay run therefore
exercises both narration types Herald produces: the periodic report and the versioned
release note.

Replay reads milestones from history; it never manufactures them. No tags are created,
no GitHub releases are cut, no changelog entries are written — replay's only outward
channel is Telegram.

## Delivery

Replayed notes go out through the normal delivery path to a Telegram channel
designated at launch — the organization's regular channel, or a dedicated one for the
run. Everything else about the channel behaves as in live delivery: the configured
language, the report formatting, the version header on a milestone. What replay adds
is only the historical dating, so a reader scrolling the channel reads the project's
evolution in sequence — which directions opened, which matured, which were dropped.

## Re-runs and bounded runs

Replay is repeatable by design — regenerating the chronicle after a prompt or model
change is one of its jobs:

- **memory writes are idempotent**: a re-run does not duplicate episodic entries or
  semantic chunks;
- **narration is regenerated fresh** on every run — the delivered texts are a
  projection of memory, not part of it, so a re-run reflects the current prompt and
  model;
- a run is **boundable** — stop after K windows, or at a given commit — so a
  small-dose check precedes a full-history pass.

## What replay is for

Two roles, one mechanism:

- **Onboarding.** A project Herald starts serving today gets its past narrated, not
  just indexed: the channel opens with the project's history already told, and live
  serving continues the same chronicle from where replay left off.
- **Acceptance.** Replay is the end-to-end complement to the
  [eval harness](narration.md#quality-is-measured-not-eyeballed). The harness pins
  fixed cases against user-authored references; replay exercises the whole pipeline —
  derivation, retrieval, reasoning, delivery — over a real history, and its quality is
  judged by reading the chronicle it produces. A generation change that survives the
  harness is confirmed by a bounded replay.

Cost stays bounded by activity: LLM generation happens once per window and once per
tag milestone — never per commit or per push.
