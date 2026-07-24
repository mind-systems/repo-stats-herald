# 3.6 — Populate and keep fresh

**Phase:** 3 — Repo mirror & semantic memory. Depends on 3.1 (mirror; an isolated tree per operation) and 3.4 (index/remove). Closes the phase: the store reflects each served repo's current artifacts on its canonical ref, and stays in sync on every canonical-ref push.

## Current state

After 3.4, Herald can index or remove one artifact from a mirror tree on demand, but nothing populates a repo's store initially or keeps it in sync as the repo changes. A served repo that already exists has an empty store; a push that edits an artifact does not update it. Worse: as originally scoped, `on_push` would index *every* branch's push — silently overwriting "what the project is now" with a feature branch's content, since semantic memory holds no branch dimension.

## Change

Sync the store to a repo's current artifacts on its **canonical ref only** — semantic memory answers "what is this project now," which has exactly one branch's worth of an answer; branches feed episodic memory and narration in later phases, never semantic memory.

- Extend `src/core/config.py` `Settings` with a canonical-ref policy (default: the repo's default branch) — configuration, related to but distinct from the delivery branch-role resolver (9.1).
- `src/knowledge/sync.py` — `KnowledgeSync`:
  - `backfill(repo: str, org_id: int)` — resolve the repo's canonical ref, open an isolated mirror tree at it (3.1's `RepoMirror.tree`), walk the tree and `ArtifactIndexer.index` each path (3.4's `SourceStrategy` selects what counts). Used on first sight of a served repo (triggered manually / on install; a small entrypoint is enough here).
  - `on_push(push: PushEvent)` — **only when `push.branch` is the repo's canonical ref**: open an isolated tree at `push.after` (3.1), then from the push's changed paths (union of added/modified/removed across its commits) `index` the added/modified paths and `remove` the deleted ones. A push on any other branch touches no semantic memory — the strategy isn't even consulted.
- Wire `on_push` into the ingestion flow: after a push passes the serve-allowlist (task 2.2), call `KnowledgeSync.on_push`.

## Files & types

- new `src/knowledge/sync.py` (`KnowledgeSync`)
- edit `src/core/config.py` (canonical-ref policy)
- edit `src/ingestion/router.py` (invoke `on_push` for a served push)

## Guards

- **Semantic memory tracks the canonical ref only — never a per-branch store.** A non-canonical push is a no-op for semantic memory by construction, checked before the mirror tree is even opened.
- Only curated-artifact paths are chunked/embedded — a push touching only code does no indexing work.
- Keyed by `(repo, path)`, current state only — the store never accumulates history; re-index replaces.
- Removed paths are deleted from the store (no orphan chunks).
- `backfill` is idempotent (re-running re-syncs + replaces, does not duplicate).
- Each mirror read is an isolated tree (3.1) — concurrent canonical-ref pushes never share a mutable tree.

## Verification

- `backfill(repo, org_id)` opens a tree at the canonical ref and populates the store with the repo's current curated artifacts; a query returns relevant chunks.
- A served push to the canonical ref editing `ROADMAP.md` re-indexes only `ROADMAP.md`; a push adding `docs/behavior/x.md` indexes it; a push deleting a doc clears its chunks.
- A served push to a **non-canonical** branch (e.g. `feature/x`) does no semantic indexing at all, regardless of what files it touches.
- A push touching only `src/*.py` on the canonical ref opens a tree but does no indexing.
