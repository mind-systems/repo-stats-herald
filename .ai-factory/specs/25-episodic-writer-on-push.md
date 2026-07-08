# 4.3 — Episodic writer on push

**Phase:** 4 — Episodic memory (the evolution log). Depends on 4.1 (the store), 4.2 (the resolver), and 3.6 (runs after the semantic sync on a served push).

## Current state

After 4.1 and 4.2, Herald can resolve a `LinkedChange` and persist an `EpisodicEntry`, but nothing connects the two on a live push — episodic memory stays empty as new pushes arrive.

## Change

Wire a served push's resolved change into the episodic store, at the composition/router layer — never inside the `episodic` package itself, which must not depend on `changelog`.

- In `src/ingestion/router.py`, after `KnowledgeSync.on_push` (3.6): call `LinkedChange.resolve` (4.2) on the mirror, map it into an `EpisodicEntry` — `content` = completed task titles + commit messages joined, `changed_at` = the timestamp of the push's head (`after`) commit — embed `content` via the `Embedder` (3.2), and `EpisodicStore.append(entry)` (4.1).
- Assembled at the composition root (`main.py`) — `EpisodicStore` constructed alongside `KnowledgeStore`, injected into the router the same way.

## Files & types

- edit `src/ingestion/router.py` (resolve → map → embed → append on a served push, after 3.6)

## Guards

- **Write-time stays cheap**: this task stores intent + change (tasks, commits, embedding) only — it does **not** derive or store the *outcome* (the narrated meaning of the change). Outcome is produced by the reasoner at read time (Phase 7+), never generated per push here.
- **The dependency runs one way**: the router imports both `episodic` and (later) `changelog`; `src/episodic/` itself never imports `src/changelog/` or anything push-shaped — it only knows `EpisodicEntry`.
- A push with no completed tasks (commits-only) still gets an entry — the episodic log records everything that happened, not only feature completions.
- A failure to append raises (visible), never silently drops history.
- This task does not touch the narrator — now the reasoner's narrate (8.1) — it reads the resolved `LinkedChange` independently; the two consumers do not depend on each other.
- The `LinkedChange` resolved here is for the **episodic write only**. Under Herald's cadence model a served push is memory-only — it is not narrated or delivered per push (narration and delivery happen later, from episodic memory, on the report and release cadences) — so nothing downstream in the router re-consumes this object on the same push.

## Verification

- A served push that completes a roadmap task → an `EpisodicEntry` with that task, its commit shas, `changed_at`, and a populated embedding appears in the store for the repo.
- A code-only push → an entry with commits only, `completed_tasks` empty.
- Two consecutive pushes → two retained entries, in order; nothing overwritten.
