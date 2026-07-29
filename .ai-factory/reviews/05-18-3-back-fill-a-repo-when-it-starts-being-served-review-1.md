# Code Review: 18.3 — Back-fill a repo when it starts being served

**Files reviewed:** `src/ingestion/router.py` (only production-code change)
**Ground truth cross-checked:** `src/knowledge/sync.py`, `src/ingestion/models.py`, `src/main.py`, spec `55`

## Change under review

Two-part edit to `src/ingestion/router.py`:
1. New module-level `_run_isolated_backfill(knowledge_sync, repo, org_id)` — wraps `knowledge_sync.backfill(repo, org_id)` in `try/except`, logging `backfill failed: repo=%s org_id=%s` on failure.
2. In the `installation`/`installation_repositories` branch, after `store.add`/`store.remove`, it reads `knowledge_sync = getattr(request.app.state, "knowledge_sync", None)` and, when present, registers one isolated backfill background task per repo in `installation_event.repos_added`.

## Correctness verification

- **Signature match** — `KnowledgeSync.backfill(repo: str, org_id: int)` (`sync.py:38`) matches the dispatched arguments. `InstallationEvent.repos_added` is `tuple[str, ...]` and `org_id` is `int` (`models.py:26-29`), so the loop passes a repo-name string and the org id exactly as `backfill` expects.
- **Placement** — dispatch happens after both `store` awaits complete and before the summary `logger.info`/`return`, matching the spec's ordering intent (served set updated first, then backfill).
- **Optional-collaborator guard** — `getattr(..., "knowledge_sync", None)` mirrors the push branch (line ~192) and is genuinely needed: `main.py` only conditionally sets `app.state.knowledge_sync`.
- **No late-binding bug** — `background_tasks.add_task` captures `repo` by value at registration time, so the per-iteration value is bound correctly; a closure over the loop variable would not be.
- **Event gating** — `_parse_installation_event` yields an empty `repos_added` for `installation` events whose action is not `created` and for unrelated actions, so no spurious backfill is dispatched; empty tuples simply skip the loop.
- **Background-task delivery on a 204** — FastAPI attaches the injected `BackgroundTasks` to any returned `Response` (including `Response(status_code=204)`), so tasks run after the response is sent and the webhook acknowledgement is not delayed.

## Guard compliance (spec `55`)

- **Isolation** — each repo runs in its own `try/except` task; one repo's failure is caught and logged, never propagating to a sibling or to the webhook response. Matches the push fan-out's `_run_isolated` semantics.
- **Idempotent repeat-add** — a repeat add simply re-dispatches `backfill`, idempotent on its own terms; no extra handling needed and none added.
- **Removal path untouched** — `store.remove`/`repos_removed` handling is unchanged; no backfill on removal.
- **Episodic out of scope** — no reference to `episodic_writer` / `HistoricalBackfill` in the new code.
- **Partial-index distinguishability** — `backfill` logs `backfill complete: repo=... files_seen=...` only after the full tree is indexed (`sync.py:51`); on failure the new wrapper logs `backfill failed: repo=... org_id=...`. A partially-indexed repo therefore carries a failure line and no completion line, distinguishing it from a successful one. This is the mechanism the spec's guard calls for and it is correctly wired.

## Findings

None. The change is minimal, correctly typed, matches the surrounding isolation pattern, and honors every guard in the spec.

REVIEW_PASS
