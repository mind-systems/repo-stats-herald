# Plan: 18.3 — Back-fill a repo when it starts being served

## Context
Wire the `installation`/`installation_repositories` webhook branch to dispatch `KnowledgeSync.backfill(repo, org_id)` per newly served repo, isolated the same way the push fan-out isolates its background tasks, so a newly installed repo's semantic memory populates without a manual `scripts/backfill.py` run.

## Settings
- Testing: no
- Logging: minimal
- Docs: no

## Tasks

### Phase 1: On-install semantic backfill

- [x] **Task 1: Add a per-repo isolated backfill runner**
  Files: `src/ingestion/router.py`
  Add a module-level async helper (alongside the existing `_run_isolated`) that runs one repo's semantic backfill in isolation, mirroring how `_run_isolated` wraps push tasks. It must accept the `knowledge_sync` object, `repo` (str), and `org_id` (int), then:
  - `await knowledge_sync.backfill(repo, org_id)` inside a `try`.
  - On `except Exception:` call `logger.exception("backfill failed: repo=%s org_id=%s", repo, org_id)` — the repo identity in the failure line is what makes a partially-indexed repo distinguishable from a successfully indexed one (`KnowledgeSync.backfill` logs `"backfill complete: repo=... files_seen=..."` only after the full tree is indexed, so absence of that line plus this exception line marks the partial state — Guards, spec `55`).
  Do not swallow-and-continue inside the loop over files; the whole repo's backfill is the isolation unit, matching `KnowledgeSync.backfill` semantics. This satisfies the guard that one repo's failure never propagates to a sibling or to the webhook acknowledgement.

- [x] **Task 2: Dispatch backfill for each added repo in the installation branch** (depends on Task 1)
  Files: `src/ingestion/router.py`
  In the `event_name in ("installation", "installation_repositories")` branch of `receive_github_webhook`, after `await store.add(...)` and `await store.remove(...)` succeed (and before the existing `logger.info("served repos updated: ...")` / return):
  - Read `knowledge_sync = getattr(request.app.state, "knowledge_sync", None)`, the same optional-collaborator pattern the `push` branch already uses at line ~192.
  - If `knowledge_sync is not None`, loop over `installation_event.repos_added` and for each repo call `background_tasks.add_task(_run_isolated_backfill, knowledge_sync, repo, installation_event.org_id)` (use the helper name chosen in Task 1). Registering as a background task keeps the webhook response un-delayed — Starlette runs these after the response is sent — and gives each repo its own isolated task.
  - Leave the `store.remove` / `repos_removed` handling and the removal path completely untouched (Guards: removal path adds no behavior).
  - Do not touch or reference `episodic_writer` / `HistoricalBackfill` here — episodic backfill is explicitly out of scope; this task wires semantic backfill only.
  Note: a repeat add of an already-served repo simply re-dispatches `backfill`, which is idempotent on its own terms (chunk rows keyed on repo/path/index, each file's write replacing that file's rows) — no extra guard needed here.
