# 5.3 — Semantic bootstrap

**Phase:** 5 — Code-derived understanding. Depends on 5.2 (the distiller), Phase 3 (the mirror, `KnowledgeSync`/3.6).

## Current state

`CodeDistiller` (5.2) can turn selected code into feature-level text on demand, but nothing turns that into a standing part of semantic memory, and nothing is reviewed before it would count as ground truth. A code-only repo has no path into the knowledge store at all today. Two hazards in the naive approach: writing the draft under a path the default `SourceStrategy` *does* select (e.g. `docs/**`) would let 3.6 auto-index an unreviewed, possibly-wrong draft into semantic memory before any human looks at it; and a re-run that overwrites a human-reviewed, already-committed artifact would clobber real work and re-poison memory with a fresh unreviewed draft.

## Change

Run the distiller once over a repo's current state, write its output to a fixed path the source strategy deliberately does not select, and let a human graduate it into the knowledge base by hand.

- `src/knowledge/bootstrap.py` — `CodeBootstrap.run(repo: str, org_id: int)`:
  - `CodeDistiller.distill` (5.2) over the mirror's current HEAD, scoped by `CodeSourceStrategy` (5.1);
  - write the result to a **fixed draft path the default `SourceStrategy` does not select** — `.ai-factory/bootstrap-draft.md` — clearly marked as LLM-generated and unreviewed. Because this path is outside the selected set (3.4.1's contract), 3.6 never indexes it, however fresh or stale it is.
  - stop there — **no direct write to `KnowledgeStore`**. A human reviews the draft, then copies/adapts its content into a curated, source-**selected** artifact (e.g. an `ARCHITECTURE.md` section, or a new selected doc) and commits *that*. The existing on-push sync (3.6) then indexes the reviewed artifact exactly like any other selected source — no new memory-writing path.

## Files & types

- new `src/knowledge/bootstrap.py` (`CodeBootstrap`)

## Guards

- **Bootstrap writes only the non-selected draft path** — never a source-selected path, and never the eventual committed, reviewed artifact. It has no way to touch either, by construction.
- **No premature indexing** — the draft's path is outside `SourceStrategy.selects`, so 3.6 never auto-indexes an unreviewed draft into "what the project is now."
- **No clobber, no re-poisoning** — because bootstrap never writes the selected/committed artifact, a re-run only refreshes the draft; a human's already-reviewed and committed work is never overwritten or reintroduced from a stale draft.
- **One-time, human-reviewed** — the draft is never trusted as ground truth; graduating it into memory is a human action (review, copy/adapt, commit), not something this task automates.
- **No new memory-writing path** — the committed, reviewed artifact flows through 3.6's existing indexer unchanged.
- Idempotent — re-running regenerates the draft at the same fixed path; it does not duplicate.

## Verification

- Bootstrapping a code-only repo (Tradeoxy) emits `.ai-factory/bootstrap-draft.md`.
- A 3.6 sync (backfill or on-push) does **not** index the draft — it stays outside semantic memory until a human acts.
- After a human copies the draft's content into a selected artifact and commits it, a semantic query (3.3's `KnowledgeStore.query`) returns chunks describing the repo's features — via the ordinary 3.6 sync path, no special-cased code.
- Re-running bootstrap refreshes `.ai-factory/bootstrap-draft.md` and leaves the already-committed, reviewed artifact untouched.
