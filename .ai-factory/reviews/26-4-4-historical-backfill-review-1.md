# Code Review — 4.4 Historical backfill (implementation)

**Scope:** `git diff HEAD` code changes for task 4.4. Reviewed the two new source files and three modified files in full, against the plan (`.ai-factory/plans/26-4-4-historical-backfill.md`) and the code they integrate with (`linked_change.py`, `writer.py`, `store.py`, `mirror.py`, `main.py`, `scripts/backfill.py`).

**Files reviewed:**
- `src/episodic/backfill.py` (new) — `EpisodicBackfill.run`
- `scripts/backfill_episodic.py` (new) — composition-root entrypoint
- `src/commits/collector.py` — `first_parent_steps` + `EMPTY_TREE_SHA`
- `src/episodic/store.py` — `recorded_commit_shas` (ABC + `PgEpisodicStore`)
- `src/github/mirror.py` — `object_store_path`

## Ground-truth verification (exact command forms the code runs)

- **Root-commit reduction holds.** `git show --end-of-options <empty-tree>:<path>` exits **128**; `LinkedChangeResolver._read_roadmap_at` uses `check=False` and returns `None` on non-zero → the root reads as "no prior roadmap" (every done-marker at root counts as newly completed). `git log --numstat --shortstat --end-of-options <empty-tree>..<root>` (the exact form `collect` uses) succeeds and yields the root commit. `commit_timestamp` on the root succeeds. So the uniform `resolve(bare, before, after)` call with `before = EMPTY_TREE_SHA` for the root is correct — no special-casing needed.
- **Merge handling is correct and idempotency-safe.** Verified on a repo with merges: `git rev-list --reverse --first-parent --parents` prints a merge line as `<merge> <p1> <p2>`. The parser takes `shas[1]` = `p1` = the **first** parent, so `before` is always the first parent and `before..after` aggregates the merged side branch into one entry. Side-branch commits are never first-parent tips, so they never appear as an `after` and cannot cause double coverage or gaps.
- **Async/await is correct.** `recorded_commit_shas` is `async def` on both the ABC and `PgEpisodicStore`, and the call site awaits it (`recorded = await self._store.recorded_commit_shas(repo)`) — the review-2 defect is fixed. `store.append` and `embedder.embed` are likewise awaited.

## Correctness checks (no issues)

- **Idempotency.** `recorded` is seeded from the union of all stored `commit_shas` for the repo (`SELECT DISTINCT unnest(commit_shas) … WHERE repo = $1`), and each appended `after` is added to the in-memory set — so re-runs, intra-run duplicate `after` values, and overlap with live 4.3 pushes are all skipped. Per-entry `INSERT` commits make an interrupted run resumable. Cross-org repo-name collision is harmless: commit SHAs are content-addressed/globally unique, so a union across orgs cannot cause a false skip.
- **Ordering / preconditions.** `run` calls `mirror.ensure` first, then `_canonical_ref` (`default_branch` reads bare `HEAD`), then `object_store_path` and `first_parent_steps` — every bare-store read is after the clone exists, satisfying `object_store_path`'s documented precondition.
- **Graceful empty/unknown ref.** `first_parent_steps` runs with `check=False` and returns `[]` on non-zero, so an unborn `HEAD` or a bad canonical-ref override yields zero steps (logged as 0) rather than raising — matching the plan's deliberate deviation from the siblings' `check=True`.
- **Empty-content guard.** `if not content: … continue` prevents embedding an empty string; as documented it is effectively unreachable for a valid first-parent step (`before..after` always yields `after`). A skipped empty step is simply never recorded and harmlessly re-skipped on re-run.
- **Writer parity.** `content`, `commit_shas = tuple(c.sha …)`, `changed_at = commit_timestamp(bare, after)` (tz-aware ISO 8601 → `timestamptz`), the `[embedding] = await embedder.embed([content])` unpack, and the full `EpisodicEntry` construction mirror `src/ingestion/writer.py` exactly.
- **Guards honored.** Resolve + embed only — no `LLMClient.generate`; reads the bare object store directly (no worktree per step); `changed_at` is always the historical commit's own timestamp; `src/episodic/backfill.py` imports only infra plus injected public classes.
- **Composition root.** `scripts/backfill_episodic.py` applies `src/episodic/schema.sql` (`CREATE TABLE IF NOT EXISTS`, idempotent — no new migration) and wires `OllamaEmbedder`, `PgEpisodicStore`, `AiFactorySourceStrategy`, `GitCommitCollector`, `LinkedChangeResolver`, the `GitHubAppAuth`/`clone_source`/`RepoMirror` trio, and `settings.canonical_refs` — matching `main.py`'s lifespan and `scripts/backfill.py`. Pool closed in `finally`. Assembly only, no logic.

## Findings

None.

REVIEW_PASS
