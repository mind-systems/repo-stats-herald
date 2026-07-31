# Code Review — 20.2.2 Give `RepoMirror` an async boundary

**Plan:** `.ai-factory/plans/11-20-2-2-give-repomirror-an-async-boundary.md`
**Spec:** `.ai-factory/specs/61-repo-mirror-async-boundary.md`
**Scope reviewed:** `git diff HEAD` — `src/github/mirror.py` (read in full), all 9 production callers, 4 scripts, and 11 test files (read `test_mirror_isolation.py` + its unchanged `tests/github/conftest.py` in full).
**Verification:** ran the non-DB affected suites — `tests/github`, `tests/versioning`, `tests/graph/test_coordination_seeder.py`, `tests/delivery/test_release_delivery.py`, `tests/knowledge/test_knowledge_sync.py`, `tests/knowledge/test_bootstrap.py` → **140 passed** (incl. the full forced-interleaving concurrency contract).

## Verdict

No correctness, security, or concurrency defects found. The conversion is faithful to the spec's guards and to 20.2.1's pinned invariants.

## What was checked and holds

- **Offload owned once (guard).** Every blocking subprocess routes through the single `_to_thread` helper (`mirror.py:255`), directly (`default_branch`) or via `_run_git` (`ensure`, `tree`, `sweep_worktrees`, `_reclaim_finished_worktrees`). No call site calls `asyncio.to_thread` itself.
- **`_reclaim_finished_worktrees` converted (the plan-review-1 fix).** It is now `async def` (`mirror.py:210`), each `worktree remove` is `await`ed (`:221`), and `ensure` awaits it (`:165`) — so the deferred removal actually runs and reclamation timing is preserved. The list snapshot/clear stays synchronous under `_finished_worktrees_lock`, so no coroutine yields between read and clear.
- **Clone-race serialization (scenario 1).** `ensure` holds a lazily-created per-repo `asyncio.Lock` across its whole body (`:146`). `_ensure_lock` (`:74`) does the get-or-create with no `await` between lookup and insert, so two coroutines racing to create the same repo's lock can't both win — verified sound for a single event loop. `test_two_overlapping_ensures_never_both_take_the_clone_branch` passes with the two-party barrier correctly removed and the surviving invariant ("clone dispatched exactly once") kept.
- **`tree` takes no lock.** Confirmed it does not acquire the ensure lock and never holds anything across `yield` (`:200-208`), so `ensure`/`tree` overlap and concurrent `tree`s stay legal — the three INAPPLICABLE scenarios and both torn-tree tests pass. No reentrant/deadlock path: `ensure` (holding the lock) never calls `tree`/`default_branch`.
- **Credential + reclamation guards.** `_run_git_sync` keeps the credential-env construction and `capture_output=True, check=True` byte-for-byte; only the process launch moved to a thread. `contextlib.suppress(subprocess.CalledProcessError)` still wraps `await self._run_git(...)` correctly (the coroutine now raises the same exception type through the `await`).
- **Caller completeness.** Independent grep of `src/` + `scripts/` for `ensure`/`tree`/`default_branch`/`sweep_worktrees`/`resolve_canonical_ref`/`.next(` shows every shelling call is `await`ed and every `tree` is `async with`; the only remaining bare references are docstrings/comments. `Versioner.next`/`_next_staging` correctly became `async` (only staging awaits `default_branch`; `_next_release` stays sync); its sole caller `ReleaseDelivery.deliver:83` awaits it. `object_store_path` and its sync consumers are untouched. `scripts/backfill.py` correctly needs no edit.
- **Ordering unchanged.** In every caller `ensure` is awaited before `tree`/`default_branch`/`resolve_canonical_ref` within the same coroutine, so the "must ensure first" contract is preserved; across coroutines the per-repo lock serializes the first-ever clone.
- **Test fakes.** All duck-typed `FakeMirror`/`_FakeMirror` `ensure`/`default_branch` became `async def` and `tree` became `@asynccontextmanager async def`; no sync fake method remains (grep-verified). The plan-layer citation in `tests/ingestion/conftest.py:41` was scrubbed per the global doc rule. `tests/ingestion/test_episodic_writer.py` correctly needed no change (it only reads fake attributes, never calls the mirror directly).
- **Gating harness.** `tests/github/conftest.py` (`GatedRunner`) is unchanged and still works: `self._run` executes inside the offloaded worker thread, so its `threading` barriers/events block the same way they did under `ThreadPoolExecutor` — the gathered coroutines' offloaded subprocesses meet at the gates as the docstrings describe.

## Non-blocking observations (optional future hardening — no change required)

1. **`asyncio.Lock` is implicitly bound to the event loop that first uses it.** If a single long-lived `RepoMirror` instance were ever driven across two different event loops (e.g. two successive `asyncio.run(...)` calls in one process reusing the same mirror), a lock created under the first loop would raise "got Future attached to a different loop" on the second. This does **not** occur in any current path — the composition roots build the mirror inside the one loop that uses it, scripts run a single `asyncio.run`, and test fixtures are function-scoped — so it is a latent fragility, not a defect. Worth a one-line note only if a future caller reuses a mirror across loops.

2. **`_ensure_locks` grows one entry per repo and is never evicted.** For Herald's bounded served-repo set this is negligible; noting only for completeness.

Neither observation affects the behavior 20.2.2 ships. The change is correct and verified.
