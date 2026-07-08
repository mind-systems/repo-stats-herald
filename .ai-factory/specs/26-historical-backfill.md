# 4.4 — Historical backfill

**Phase:** 4 — Episodic memory (the evolution log). Depends on 4.1 (the store) and 4.2 (the resolver). Closes the phase: episodic memory holds a repo's past, not just its changes from deploy-time forward.

## Current state

After 4.3, every new served push appends to episodic memory — but a repo that already exists when Herald starts serving it has no entries for its prior history. "What did we build 6 months ago" is unanswerable until 6 months of live pushes have accumulated.

## Change

Replay a repo's full commit history through the resolver, appending one episodic entry per historical change, evaluating the source strategy at the tree state that existed at the time — not against HEAD.

- `src/episodic/backfill.py` — `EpisodicBackfill.run(repo: str, org_id: int)`:
  - Walk the mirror's commit history in order (oldest first) — each step's `before`/`after` pair is one historical change.
  - For each step: check out (or diff against) the tree **as it stood at that commit**, apply the source strategy to *that* tree state (an early commit may predate the roadmap entirely — commits-only; a later commit may have a mature roadmap — task-anchored), call `LinkedChange.resolve` (4.2) against that step's range, map to an `EpisodicEntry` with `changed_at` = that step's commit timestamp, embed `content`, `EpisodicStore.append` (4.1).
  - Per-historical-tree evaluation is the point: harness richness is not constant across a project's life, so the resolved intent-anchoring strength varies entry to entry, matching how the project actually was at each point (see `docs/concepts/derivation-modes.md`).
- A small entrypoint (manual / on first sight of a served repo) triggers it — same trigger shape as 3.6's `backfill`.

## Files & types

- new `src/episodic/backfill.py` (`EpisodicBackfill`)

## Guards

- **No per-change LLM generation** — backfill is resolve + embed only, matching 4.3's write-time-cheap guard; the outcome is still read-time, not backfilled.
- `changed_at` is always the **historical** commit's own timestamp, never the backfill run's time.
- **Idempotent** — re-running backfill for an already-backfilled repo does not duplicate entries (key the run on `repo` + the commit range already covered, or a backfill watermark).
- Reads the mirror only, no network fetch beyond what `RepoMirror.ensure` already needs.
- **Per-step tree reads should not spin a full worktree per historical commit** — under 3.1's worktree-per-operation model, `git worktree add`/`remove` for every historical step would churn expensive filesystem operations over a long history. Read blobs directly by SHA (`git cat-file`/`git archive` against the bare object store) instead — the per-step tree state only needs to answer "what does the source strategy select and what's in it," not a full working-tree checkout.

## Verification

- Backfilling a repo with N historical roadmap-completing commits produces N (or more, including commits-only steps) episodic entries spanning its full history, each with the correct `changed_at`.
- A `query(embedding, k, since=<6 months ago>, until=<3 months ago>)` against a backfilled repo returns only entries from that window.
- Re-running backfill on an already-backfilled repo does not create duplicate entries.
