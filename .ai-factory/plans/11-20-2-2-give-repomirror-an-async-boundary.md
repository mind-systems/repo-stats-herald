# Plan: 20.2.2 — Give `RepoMirror` an async boundary

## Context
Move `RepoMirror`'s blocking git work (`ensure`, `tree`, `default_branch`, `sweep_worktrees`) off the event loop onto a thread it owns internally, make those methods awaitable, and update every caller — so a long `git fetch`/`clone` no longer stalls the loop, while worktree isolation, credential handling, and deferred reclamation timing stay unchanged. The synchronization needed to keep the concurrency invariants pinned by 20.2.1 (`tests/github/test_mirror_isolation.py`) is this task's to choose.

## Ground-truth notes (spec vs. code)
- **DEVIATION: spec said `src/ingestion/router.py` (release fan-out's mirror call) / file shows the fan-out already lives in `src/delivery/service.py` (`ReleaseDelivery.deliver`, calls `self._mirror.ensure` at line 81) / router.py has no mirror reference at all.** 20.1 moved the fan-out; the mirror call to convert is in `service.py`, not `router.py`.
- **DEVIATION: spec's `Files & types` omits callers the code proves reachable / files show them / they are included below.** `default_branch` also flows through `resolve_canonical_ref` and `Versioner._next_staging`; `ensure`/`tree`/`resolve_canonical_ref` are also called by `src/episodic/backfill.py`, `src/knowledge/bootstrap.py`, and `src/changelog/report.py` (`TimeWindow.resolve`). Ground truth wins; all are covered.
- `object_store_path` does **not** shell out (pure path return) — it stays synchronous, and its callers (`Versioner`, the changelog sections, `EpisodicBackfill`, `TimeWindow`) keep calling it synchronously. Do not touch it.
- `resolve_canonical_ref` (module function in `mirror.py`) calls `default_branch`, so it becomes `async` and every caller must `await` it.
- `scripts/backfill.py` constructs a mirror but calls no shelling method directly (it delegates to `KnowledgeSync.backfill`), so it needs **no** edit.

## Settings
- Testing: yes — but only conversion of the existing mirror suites to the awaitable API and the one red-scenario relaxation the spec's guard mandates; no net-new coverage.
- Logging: minimal — log lines and levels are unchanged (guard: "same log lines").
- Docs: no.

## Tasks

### Phase 1: The async boundary inside `RepoMirror`

- [x] **Task 1: Make `RepoMirror`'s shelling-out methods awaitable behind one owned thread-offload**
  Files: `src/github/mirror.py`
  Convert `ensure`, `default_branch`, `sweep_worktrees`, and the shared `_reclaim_finished_worktrees` helper to `async def`, and `tree` from `@contextlib.contextmanager` to `@contextlib.asynccontextmanager async def` (its `worktree add` on enter is offloaded; the `finally` append under `_finished_worktrees_lock` runs on the loop thread, no offload). Make `resolve_canonical_ref` `async` (it awaits `mirror.default_branch`).
  - **`_reclaim_finished_worktrees` also shells out and must convert with them.** `ensure` calls `self._reclaim_finished_worktrees(bare_path)` (line 127), and that helper loops `self._run_git("worktree", "remove", ...)` (lines 165–182). Whichever offload mechanism is chosen, this helper must run its removals on the offload thread: if `_run_git` becomes `async def`, make `_reclaim_finished_worktrees` `async def`, `await` each removal, and change the `ensure` call site to `await self._reclaim_finished_worktrees(bare_path)`. A helper left synchronous while `_run_git` is a coroutine would call the coroutine unawaited — no subprocess runs, `contextlib.suppress(subprocess.CalledProcessError)` catches nothing, and the deferred worktree removal silently never happens, breaking the reclamation-timing guard. The list snapshot/clear under `_finished_worktrees_lock` stays synchronous (no offload); only the `worktree remove` calls are offloaded.
  - **Offload owned once (guard):** route the blocking `self._run(...)` through a single private async helper (e.g. `async def _run_git(... )` wrapping `await asyncio.to_thread(...)`, or a thin `_to_thread` around the existing sync body). The blocking process call is offloaded inside `RepoMirror` only — never at a call site. Keep `_run_git`'s credential-env construction and `capture_output=True, check=True` exactly as today (credential handling unchanged).
  - **Serialization is the design decision (per spec + 20.2.1):** offloading `ensure`'s body adds yield points at each `await`, so two concurrent `ensure` coroutines for a never-cloned repo can both pass the `bare_path.exists()` check and both clone — the RED scenario `test_two_overlapping_ensures_never_both_take_the_clone_branch`. Introduce per-repo serialization so a clone is dispatched **at most once** and the reclaim snapshot/clear stays consistent; the natural answer (which 20.2.1 flagged as "one plausible answer") is a lazily-created per-repo `asyncio.Lock` held across the whole `ensure(repo)`. Do **not** hold that lock across `tree`'s `yield` (a consumer holds the worktree open arbitrarily long) and do **not** take it in `tree` — `test_worktree_prune_does_not_race_a_worktree_being_created` and `test_ensure_overlapping_an_open_tree_does_not_disturb_it` are INAPPLICABLE (git already handles those safely), so `tree` and `ensure` must remain able to overlap.
  - Keep the existing `threading.Lock` around `_finished_worktrees`; the append and the snapshot/clear now both run on the loop thread, but keeping the lock preserves the pinned bookkeeping-consistency invariant unchanged.
  - Reclamation timing is unchanged: a finished worktree is still reclaimed on the repo's next `ensure`, never in `tree`'s `finally`.
  - Update the class/method docstrings only where the shape changed (e.g. `tree` is now an async context manager); describe present behavior, no plan-layer references.

### Phase 2: Convert production callers to `await`

- [x] **Task 2: Ripple `default_branch` async through the versioner** (depends on Task 1)
  Files: `src/versioning/versioner.py`
  `_next_staging` calls `self._mirror.default_branch(repo)`; make `_next_staging` and the public `next` `async def` and `await` the call. `_next_release` calls no shelling method — it stays synchronous, and `next` calls it without `await`. `object_store_path`/`list_tags`/collector calls are unchanged.

- [x] **Task 3: Await the mirror and the versioner in the release fan-out** (depends on Task 1, Task 2)
  Files: `src/delivery/service.py`
  In `ReleaseDelivery.deliver`: `await self._mirror.ensure(event.repo, event.org_id)` (line 81) and `version = await self._versioner.next(...)` (line 83). No other change.

- [x] **Task 4: Await the mirror in the knowledge-sync and coordination paths** (depends on Task 1)
  Files: `src/knowledge/sync.py`, `src/graph/coordination.py`
  In both, make the `_canonical_ref` helper `async def` (it awaits `resolve_canonical_ref`) and `await` it at each call site. `await self._mirror.ensure(...)` and `async with self._mirror.tree(...) as tree:` in `KnowledgeSync.backfill`/`on_push` and `CoordinationSeeder.seed`. The inner file-walk / read logic is synchronous and unchanged.

- [x] **Task 5: Await the mirror in the episodic-write, episodic-backfill, and bootstrap paths** (depends on Task 1)
  Files: `src/ingestion/writer.py`, `src/episodic/backfill.py`, `src/knowledge/bootstrap.py`
  - `EpisodicWriter.write`: `await self._mirror.ensure(...)`; `async with self._mirror.tree(...) as tree:`.
  - `EpisodicBackfill`: make `_canonical_ref` `async def` and `await` it; `await self._mirror.ensure(...)` in `run`. `object_store_path` stays synchronous.
  - `CodeBootstrap.run`: `await self._mirror.ensure(...)`; `async with self._mirror.tree(...) as tree:`.

- [x] **Task 6: Await `resolve_canonical_ref` in the report window** (depends on Task 1)
  Files: `src/changelog/report.py`
  In `TimeWindow.resolve` (already `async`), `ref = await resolve_canonical_ref(repo, self.canonical_refs, self.mirror)`. `object_store_path` and the collector calls stay synchronous. `report_for_schedule`/`Report.build` need no change.

- [x] **Task 7: Await `sweep_worktrees`/`ensure`/`resolve_canonical_ref` in the composition roots** (depends on Task 1)
  Files: `src/main.py`, `scripts/report.py`, `scripts/bootstrap.py`, `scripts/backfill_episodic.py`
  - `src/main.py` `lifespan`: `await mirror.sweep_worktrees()` (line 89).
  - `scripts/report.py` `_run`: `await mirror.sweep_worktrees()` (89), `await mirror.ensure(...)` (120), `await resolve_canonical_ref(...)` (126).
  - `scripts/bootstrap.py` `_run`: `await mirror.sweep_worktrees()` (44).
  - `scripts/backfill_episodic.py` `_run`: `await mirror.sweep_worktrees()` (62).
  Every one already runs inside an `async` entrypoint driven by `asyncio.run` — add no new `asyncio.run` (guard). `scripts/backfill.py` needs no edit (no direct mirror shelling call).

### Phase 3: Convert the test suites and relax the mandated red scenario

- [x] **Task 8: Convert the single-threaded mirror suites to the awaitable API** (depends on Task 1)
  Files: `tests/github/test_mirror_lifecycle.py`, `tests/github/test_mirror_credentials.py`, `tests/github/conftest.py`
  Mechanical per the lifecycle file's own header ("converts this file mechanically without re-deciding any [assertion]"): make the test functions `async`, `await mirror.ensure/default_branch/sweep_worktrees`, and `async with mirror.tree(...)`. The `mirror`/`build_gated_mirror` fixtures keep the unchanged `RepoMirror` constructor signature; `GatedRunner` still gates on the sync `run` callable, which now executes on the offload thread — so its threading barriers/events keep working. Adjust the `conftest` fixtures only if the async conversion requires it (e.g. any direct `ensure` call inside a fixture).

- [x] **Task 9: Convert the concurrency suite and relax the clone-race forcing harness** (depends on Task 1, Task 8)
  Files: `tests/github/test_mirror_isolation.py`
  Rewrite the six scenarios to drive concurrency through the now-awaitable methods (e.g. `asyncio.gather` of two `ensure` coroutines, whose offloaded subprocesses still hit the `GatedRunner` gates on worker threads). The three INAPPLICABLE scenarios and the two torn-tree tests keep asserting the same invariants. For `test_two_overlapping_ensures_never_both_take_the_clone_branch`: per the spec guard, its two-party `threading.Barrier(2)` on `clone` is red-only by construction — once `ensure` is serialized only one coroutine reaches the clone gate and the barrier would hang. Relax the forcing harness (drop/replace the two-party barrier) so the surviving assertion is **"a clone is dispatched at most once"**; keep the assertion, replace the mechanism that forced the defect.

- [x] **Task 10: Convert the duck-typed mirror fakes across the other suites** (depends on Task 1)
  Files: `tests/knowledge/test_knowledge_sync.py`, `tests/ingestion/conftest.py`, `tests/ingestion/test_episodic_writer.py`, `tests/knowledge/test_bootstrap.py`, `tests/graph/test_coordination_seeder.py`, `tests/episodic/test_backfill.py`, `tests/episodic/test_backfill_store.py`, `tests/versioning/test_versioner.py`, `tests/delivery/test_release_delivery.py`, `tests/changelog/test_time_window.py`
  Each fake/stub `RepoMirror` must match the new API: `ensure`/`default_branch` become `async def`, and the fake `tree` becomes an `@contextlib.asynccontextmanager async def` consumed with `async with`. In `tests/versioning/test_versioner.py` the fake `default_branch` becomes `async` and `Versioner.next` is now awaited. In `tests/delivery/test_release_delivery.py` the fake `mirror.ensure` and fake `versioner.next` become `async` and are awaited. Where a suite uses a real `RepoMirror` (`tests/changelog/test_time_window.py`), await any direct shelling call the test makes.
  While editing, scrub plan-layer citations the global doc rules forbid: rewrite the comments at `tests/ingestion/conftest.py:41` ("roadmap 20.2.2 will make it [async]") and any sibling ("`tree` is sync today") to describe the present async behavior with no roadmap/plan reference.
