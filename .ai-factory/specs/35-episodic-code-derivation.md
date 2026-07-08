# 5.4 — Episodic code-derivation

**Phase:** 5 — Code-derived understanding. Depends on 5.2 (the distiller), 4.4 (the historical backfill it extends).

## Current state

4.4's historical backfill replays a repo's commit history through `LinkedChange.resolve` (4.2) at each step, evaluating the source strategy against the tree state at that commit. Where a historical commit predates any harness, `LinkedChange.resolve` has no roadmap to anchor to and falls back to commits-only — the *episodic* entry never distills the *semantic* half (what the code does) for that stretch of history.

## Change

Extend the historical backfill so a pre-harness commit's episodic entry is derived from code, not just left commits-only.

- In `EpisodicBackfill.run` (4.4), per historical step: evaluate the source strategy at that tree state (unchanged from 4.4) — where it selects only code (no harness yet, per `CodeSourceStrategy`, 5.1), derive that step's entry via `CodeDistiller` (5.2) over the changed code instead of `LinkedChange.resolve`'s roadmap-anchoring; where the harness exists, use the resolver (4.2) as 4.4 already does.
- Both paths still produce an `EpisodicEntry` (4.1) — `content` from the distilled feature text (code-derived steps) or the resolved tasks/commits (artifact-derived steps), `changed_at` the historical commit's timestamp either way — embedded and appended identically.
- Code-derived and artifact-derived entries **coexist** along the same repo's timeline, as the harness matures (see `docs/concepts/derivation-modes.md`).

## Files & types

- edit `src/episodic/backfill.py` (`EpisodicBackfill.run` — per-step mode selection between the resolver and the distiller)

## Guards

- **Standing/automated, not human-reviewed** — unlike the one-time semantic bootstrap (5.3), history is too large to review commit-by-commit; this path runs unattended, same discipline as 4.4's existing resolver-based path.
- Per-historical-tree evaluation — the choice between resolver and distiller is made fresh at each step, not fixed for the whole repo.
- Early (pre-harness) entries are coarser by nature — a code-distilled entry is not held to the roadmap-anchored entry's precision.
- Distillation still runs in bounded units (per 5.2's guard) — a long history does not mean one large prompt per step.
- Idempotent — matches 4.4's existing idempotency guard; re-running does not duplicate entries.

## Verification

- Backfilling a code-only repo's full history populates episodic memory with feature-level entries spanning its life.
- Early entries (before any harness existed) are code-derived (via 5.2); later entries (after a harness was adopted) are artifact-anchored (via 4.2) — both present in the same repo's log.
- A repo backfilled entirely pre-harness has every entry code-derived; a repo backfilled entirely post-harness (per 4.4's existing behavior) is unaffected by this task.
