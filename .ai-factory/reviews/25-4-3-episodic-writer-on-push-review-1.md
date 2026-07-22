# Code Review — 4.3 Episodic writer on push (review 1)

**Change reviewed:** `git diff HEAD` — code files only
**Code files changed:** `src/ingestion/writer.py` (new), `src/commits/collector.py`, `src/main.py`, `src/ingestion/router.py`
**Governing spec:** `.ai-factory/specs/25-episodic-writer-on-push.md`
**Plan:** `.ai-factory/plans/25-4-3-episodic-writer-on-push.md`
**Risk level:** 🟢 Low — implementation matches the plan and the spec; one runtime-coupling finding worth addressing, plus one edge note.

## What was verified correct

- **Type/attribute usage all checks out against ground truth.** `LinkedChangeResolver.resolve(str(tree), before, after)` takes plain strings; `change.commits.commits` is `tuple[Commit, ...]` with `.sha`/`.message`; the `EpisodicEntry(...)` kwargs exactly match its dataclass fields (`recorded_at` correctly left defaulted); `[embedding] = await embedder.embed([content])` destructures safely because `OllamaEmbedder` enforces `len(embeddings) == len(texts)`.
- **`commit_timestamp` is correct.** `git show -s --format=%cI --end-of-options <ref>` yields a single offset-aware ISO-8601 line; `.strip()` removes the trailing newline (the prior review's fix landed) so `datetime.fromisoformat` returns an aware `datetime`, which asyncpg accepts for the `changed_at timestamptz` column. `from datetime import datetime` import is correct.
- **Schema gap closed.** `EPISODIC_SCHEMA_PATH` is executed unconditionally in the lifespan `pool.acquire()` block alongside the other two schemas — `episodic_entries` now exists before any `append`, and `CREATE TABLE IF NOT EXISTS` keeps it idempotent.
- **Composition root wiring is clean.** `episodic_store` local avoids shadowing the `store` (`PgVectorStore`) binding; `strategy`, `embedder`, and `mirror` are reused rather than rebuilt; the writer sits in the settings-gated block so it is only enabled when the mirror is.
- **Router stays thin and test-safe.** `getattr(request.app.state, "episodic_writer", None)` mirrors the `knowledge_sync` guard, so the webhook contract tests (which build `TestClient(app)` without running `lifespan`) keep returning 200. Registration after `knowledge_sync` matches the spec's "after the semantic sync" ordering.
- **Spec boundary held.** No push-shaped module landed under `src/episodic/`; the writer lives in `src/ingestion/` and depends only on episodic's public classes. `src/episodic/` still knows only `EpisodicEntry`.

## Findings

### 1. A `KnowledgeSync.on_push` failure silently suppresses the episodic write for that push (correctness / robustness)

`src/ingestion/router.py:87-93` registers both background tasks on the same `BackgroundTasks` instance, `knowledge_sync.on_push` first, then `episodic_writer.write`. Starlette runs them sequentially and **stops on the first exception** (verified against the installed `starlette/background.py`):

```python
async def __call__(self) -> None:
    for task in self.tasks:
        await task()   # raises → remaining tasks never run
```

So if `knowledge_sync.on_push` raises (a transient embedding/HTTP error, a mirror fetch failure, a Postgres blip during `upsert`), `episodic_writer.write` is never invoked and that push produces **no episodic entry** — with no error attributable to the episodic path.

This contradicts:
- `EpisodicWriter`'s own docstring — *"Self-contained … so it produces an entry for every served push regardless of ordering with `KnowledgeSync`."* The self-contained `mirror.ensure` makes it independent of ordering *effects*, but not of a *preceding failure* aborting the task chain.
- Spec guard line 24/25 — the episodic log "records everything that happened" and "a failure to append raises (visible), never silently drops history." Here history is dropped not by an append failure but by an unrelated sibling task's failure, which is exactly the silent-drop the guard warns against.

**Failure scenario:** A served push to the canonical ref where the knowledge store's embedding call times out inside `on_push`. Semantic sync fails (logged), the loop aborts, `episodic_writer.write` never runs, and the push is permanently absent from episodic memory even though the resolve→embed→append path would have succeeded.

**Suggested fix (pick one):**
- Have each background task guard its own body (log-and-swallow inside `on_push` / `write`), so one failing task cannot abort the other; or
- Schedule them so they are not coupled in a single sequential chain (e.g. wrap each `add_task` target so its exception is isolated).

Register-order (episodic after semantic) can stay as-is; only the failure isolation needs fixing. Severity is bounded by the fact that this is best-effort background processing with no retry either way, but the change does make the episodic write strictly less reliable than the writer's design intends.

### 2. Edge: an empty-range push yields empty `content` → `embed([""])` may raise (minor)

If a push resolves to zero commits **and** zero completed tasks (e.g. a force-push that rewinds so `before..after` is empty), `content` is `""`. `OllamaEmbedder.embed([""])` does not hit the `if not texts` short-circuit (the list is non-empty), so it posts `input=[""]`; if the backend returns an empty/absent vector, the embedder raises `ValueError` and the write fails. Normal pushes always carry ≥1 commit message, so this is a narrow edge, not a mainline defect. No action required unless empty-range pushes are expected; worth a one-line guard (skip the append when `content` is empty) if they are. Note the related branch-delete case (`after = "0"*40`) fails earlier and louder at `mirror.tree(...)`, consistent with the spec's raise-on-failure guard.

## Verdict

Core logic, wiring, types, and the schema fix are correct and match the plan. Finding 1 (background-task failure coupling) is the one item I'd address before considering this robust against the spec's "records everything" guarantee; finding 2 is an optional edge hardening.
