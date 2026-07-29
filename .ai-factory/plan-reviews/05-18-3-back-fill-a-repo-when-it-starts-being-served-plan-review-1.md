## Plan Review Summary

**Plan:** 18.3 — Back-fill a repo when it starts being served
**Files Reviewed:** plan + `src/ingestion/router.py`, `src/knowledge/sync.py`, `src/ingestion/models.py`, `src/main.py`, spec `55`, ROADMAP contract line 22
**Risk Level:** 🟢 Low

### Context Gates
- **Roadmap (`ROADMAP.md` line 22, task 18.3):** ALIGNED. The plan matches the contract line: dispatch a backfill per added repo after `store.add`, isolated in the push-fan-out style; removal path untouched; episodic (4.4/`HistoricalBackfill`) out of scope.
- **Governing spec (`.ai-factory/specs/55-on-install-knowledge-backfill.md`):** ALIGNED. Every guard is honored — per-repo isolation (Task 1), idempotent repeat-add (Task 2 note), removal path untouched (Task 2), episodic out of scope (Task 2), and the partial-index distinguishability guard (spec §Guards, line 23) is satisfied by Task 1's `logger.exception("backfill failed: repo=%s org_id=%s", ...)` carrying repo identity.
- **ARCHITECTURE.md dependency rules:** ALIGNED. The router keeps `knowledge_sync` as a duck-typed optional collaborator via `getattr(request.app.state, "knowledge_sync", None)` — identical to the existing push branch (line 192). No new cross-feature import of `KnowledgeSync` is introduced, preserving the "features depend on infra, wired only at the composition root" rule.
- **RULES.md:** empty by design; nothing to enforce.

### Correctness verification against ground truth
- **`KnowledgeSync.backfill(repo, org_id)` signature** (`src/knowledge/sync.py:38`) — matches the plan's call exactly (`repo: str`, `org_id: int`).
- **`InstallationEvent.repos_added` / `.org_id`** (`src/ingestion/models.py:26-29`) — exist and typed as the plan assumes; `repos_added` is a `tuple[str, ...]`, so the per-repo loop yields repo-name strings, which is precisely what `backfill` expects.
- **Insertion point** — the `event_name in ("installation", "installation_repositories")` branch (router lines 227-242) does exactly what the plan describes: allowlist check → `store.add` → `store.remove` → `logger.info(...)` → `return Response(status_code=204)`. The plan's "after add/remove succeed, before the info log/return" placement is accurate.
- **Optional-collaborator pattern** — the `getattr(..., None)` guard referenced "at line ~192" is correct (line 192-194), and `main.py` only conditionally sets `app.state.knowledge_sync` (line 92), so the `is not None` guard is genuinely needed. Good.
- **Background-task delivery on a plain `Response`** — the installation branch returns `Response(status_code=204)`, not a `JSONResponse` like the push branch. This is safe: FastAPI attaches the injected `BackgroundTasks` to any returned `Response` whose `.background` is unset, so tasks added in this branch will run after the 204 is sent. The plan's claim that registering keeps the response un-delayed holds.
- **New helper vs. reusing `_run_isolated`** — justified. The existing `_run_isolated(label, task, event)` calls `task(event)` with a single `PushEvent`; backfill needs `(repo, org_id)`, a different shape. A dedicated `_run_isolated_backfill(knowledge_sync, repo, org_id)` is cleaner than contorting the existing helper, and mirrors its try/except-and-log structure.
- **Sequential isolation semantics** — Starlette runs the N per-repo tasks in one event sequentially; the per-task `except Exception` ensures one repo's failure cannot abort a sibling queued on the same `BackgroundTasks`, exactly as `_run_isolated`'s docstring describes. Cross-request overlap of the same repo is acknowledged by spec §Guards line 23 and handled by the same isolation+log path.

### Critical Issues
None.

### Positive Notes
- The plan grounds the partial-index guard in a real, verified detail: `KnowledgeSync.backfill` emits `"backfill complete: repo=... files_seen=..."` only after the full tree is indexed (`sync.py:51`), so the absence of that line plus the new exception line genuinely marks the partial state. This is a correct reading of the code, not an assumption.
- Scope discipline is precise: episodic backfill / `EpisodicWriter` explicitly excluded, removal path explicitly left untouched, idempotency reasoning tied to the actual chunk-row keying — all matching the spec's guards.
- Dependency ordering (Task 2 depends on Task 1) is stated, and both tasks touch only the one file the spec authorizes (`src/ingestion/router.py`).

PLAN_REVIEW_PASS
