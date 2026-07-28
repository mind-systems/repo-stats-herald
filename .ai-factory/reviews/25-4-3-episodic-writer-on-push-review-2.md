# Code Review — 4.3 Episodic writer on push (review 2, re-review after fixes)

**Change reviewed:** `git diff HEAD` — code files only
**Code files changed:** `src/ingestion/writer.py` (new), `src/ingestion/router.py`, `src/commits/collector.py`, `src/main.py`
**Prior review:** `.ai-factory/reviews/25-4-3-episodic-writer-on-push-review-1.md`
**Risk level:** 🟢 Low — the one substantive finding is fixed correctly; no new issues.

## Verdicts on prior-review findings

### Finding 1 — `KnowledgeSync.on_push` failure silently suppresses the episodic write → **FIXED**

The router now wraps each push background task in an isolation helper so one task's exception cannot abort its sibling. Current content of `src/ingestion/router.py`:

```python
19  async def _run_isolated(label: str, task: Callable[[PushEvent], Awaitable[None]], event: PushEvent) -> None:
20      """Runs one push background task in isolation, so its failure cannot abort
21      a sibling task queued on the same `BackgroundTasks` (Starlette runs them
22      sequentially and stops at the first exception)."""
23      try:
24          await task(event)
25      except Exception:
26          logger.exception("push background task failed: %s", label)
```

and the registrations (lines 98-104):

```python
98   knowledge_sync = getattr(request.app.state, "knowledge_sync", None)
99   if knowledge_sync is not None:
100      background_tasks.add_task(_run_isolated, "knowledge_sync.on_push", knowledge_sync.on_push, event)
102  episodic_writer = getattr(request.app.state, "episodic_writer", None)
103  if episodic_writer is not None:
104      background_tasks.add_task(_run_isolated, "episodic_writer.write", episodic_writer.write, event)
```

This resolves the coupling: because each `add_task` target is `_run_isolated`, which catches `Exception` and logs it, a failure inside `knowledge_sync.on_push` no longer aborts the task loop before `episodic_writer.write` runs. The episodic write now executes for every served push regardless of the semantic sync's outcome, matching the writer's docstring and the spec's "records everything" guard.

Verification of the fix's own correctness:
- `from collections.abc import Awaitable, Callable` is imported (line 5), so the annotation resolves.
- `add_task(_run_isolated, label, method, event)` passes the bound coroutine method as `task`; `await task(event)` invokes it correctly — both `on_push` and `write` take a single `PushEvent`.
- `except Exception` (not `BaseException`) leaves `CancelledError`/`SystemExit` to propagate — task cancellation still works.
- The spec's "a failure to append raises (visible)" intent is preserved: an append failure is now surfaced via `logger.exception` (ERROR-level traceback) rather than silently dropped. In a post-response background task there is no caller to raise to anyway, so logging is the correct visibility channel, and it is strictly louder than the pre-fix behavior for the episodic path.

### Finding 2 — empty-range push → `embed([""])` may raise → **Not fixed (was optional; now non-blocking)**

`src/ingestion/writer.py:45-46` is unchanged:

```python
45  content = "\n".join([*change.completed_tasks, *(c.message for c in change.commits.commits)])
46  [embedding] = await self._embedder.embed([content])
```

No empty-`content` guard was added. This was flagged as optional in review 1, and the Finding 1 fix further reduces its impact: if `embed([""])` raises on an empty-range push, `_run_isolated` now catches and logs it rather than letting it escape, so the worst case is a single logged failure and no entry for that (empty) push — no crash, no impact on the semantic sync. Realistic pushes always carry ≥1 commit message, so `content` is non-empty in practice. Left as a non-blocking observation below.

## Full re-review for new issues

Re-read all four changed files in full. `src/commits/collector.py` (`commit_timestamp`), `src/main.py` (schema execution + wiring), and `src/ingestion/writer.py` are unchanged from review 1 and were verified correct there (types, `.strip()` before `fromisoformat`, unconditional `EPISODIC_SCHEMA_PATH` execution, `episodic_store` non-shadowing, reuse of `strategy`/`embedder`/`mirror`, `getattr` router guard keeping the contract tests green). The only new code is `_run_isolated` and the two rewritten registration lines, reviewed above. No new correctness, security, race, migration, or type issues found.

## Deferred observations (non-blocking)

- **Empty-`content` edge (finding 2):** optionally skip the append when `content == ""` if empty-range/rewind pushes are expected; otherwise no action — the failure is now logged, not fatal. [dismissed]
- **Double mirror refresh (carried from review 1 / the plan):** both `on_push` and `write` independently call `mirror.ensure` + open a worktree at `push.after` per push. Acceptable cost of the self-contained design; a shared per-push refresh step is the natural future optimization if push volume grows. [dismissed]

REVIEW_PASS
