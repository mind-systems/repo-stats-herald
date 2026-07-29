## Code Review — 20.2.1 Concurrency contract for the async mirror (red scenarios)

**Files reviewed (code):** `tests/github/conftest.py`, `tests/github/test_mirror_isolation.py` (read in full, with `src/github/mirror.py` as ground truth). Doc/spec changes (`ROADMAP.md`, specs `61`/`66`, plan, plan-reviews, plan JSON) reviewed for consistency but are not code.

**Scope note:** guard honored — no file under `src/` changed; the harness is injected through `RepoMirror`'s existing `run` seam, exactly as `_RecordingRunner` does. The `GatedRunner`/`build_gated_mirror` design is sound and the argv-gating (`command[:len(key)] == key`) correctly distinguishes `clone`/`fetch`/`worktree add`/`worktree prune`. Test 2 and Test 5 are correct. Two defects below block the two INAPPLICABLE scenarios.

---

### Finding 1 — CRITICAL: Tests 3 and 4 hang indefinitely at their post-concurrency cleanup `ensure`

`GatedRunner.add_gate` registers a gate permanently (it is never cleared), and `__call__` consults the gate registry on **every** dispatched command for the life of the runner. Both Test 3 and Test 4 back their gates with a `threading.Barrier(2)`, then — after the concurrent section — call `mirror.ensure(...)` a final time **on the single main thread** to flush deferred reclamation. That cleanup `ensure` re-hits a still-registered barrier gate with only one party, and `Barrier(2).wait()` (no timeout) blocks forever.

- **Test 4** (`test_worktree_prune_does_not_race_a_worktree_being_created`, cleanup at line 186): gates are `("worktree","add")` and `("worktree","prune")` on `barrier`. `ensure` unconditionally runs `git worktree prune` at its end (`src/github/mirror.py:131`). The final `mirror.ensure(REPO, ORG_ID)` therefore reaches the `("worktree","prune")` gate → `reached.set()` → `barrier.wait()` with a single party → **deadlock**.
- **Test 3** (`test_finished_worktree_bookkeeping_stays_consistent_under_thread_concurrency`, cleanup at line 141): gates are `("fetch",)` and `("worktree","add")` on `barrier`. `ensure` runs `git fetch --prune origin` whenever the bare store already exists (`src/github/mirror.py:120-125`). The final `mirror.ensure(REPO, ORG_ID)` reaches the `("fetch",)` gate → `barrier.wait()` with a single party → **deadlock**.

The barrier is cyclic and trips cleanly during the concurrent section (both parties arrive), so it is *reset*, not broken — the lone cleanup `wait()` blocks rather than raising `BrokenBarrierError`. Either way the test never completes; with no per-test timeout in the suite this hangs `make test` itself.

**Failure scenario:** run `uv run pytest tests/github/test_mirror_isolation.py` → `test_finished_worktree_bookkeeping_stays_consistent_under_thread_concurrency` reaches line 141, the cleanup `ensure`'s `git fetch` hits the fetch gate, `barrier.wait()` blocks with one party, and the test (and the run) hangs indefinitely. `test_worktree_prune_does_not_race_a_worktree_being_created` hangs identically at line 186 via the prune gate.

Test 5 avoids this precisely because it gates on a `threading.Event` that it `release.set()`s before cleanup, so its own cleanup `ensure` sails through the already-set gate. The fix must give Tests 3 and 4 the same property — e.g. add a way to clear/disable gates after the concurrent section (and call it before the cleanup `ensure`), or gate on pre-settable `Event`s coordinated by a separate rendezvous rather than reusing a `Barrier` that the single-threaded cleanup will re-enter. Whatever the mechanism, no gate that requires a second party may remain live when a single-threaded `ensure` runs.

---

### Finding 2 — BLOCKER: all four scenario docstrings are unfilled placeholders

Every new scenario carries a literal placeholder docstring instead of the required prose:

- `test_two_overlapping_ensures_never_both_take_the_clone_branch` → `"""PLACEHOLDER_TASK2_DOCSTRING"""` (line 73)
- `test_finished_worktree_bookkeeping_stays_consistent_under_thread_concurrency` → `"""PLACEHOLDER_TASK3_DOCSTRING"""` (line 103)
- `test_worktree_prune_does_not_race_a_worktree_being_created` → `"""PLACEHOLDER_TASK4_DOCSTRING"""` (line 150)
- `test_ensure_overlapping_an_open_tree_does_not_disturb_it` → `"""PLACEHOLDER_TASK5_DOCSTRING"""` (line 190)

The spec's verification clause and the plan both require each scenario to state, in identifier-free prose, whether it is **red against today's synchronous mirror** or **inapplicable** and *why* — the core deliverable of a "red scenarios" task ("each states which of the two it is"). Leaving raw `PLACEHOLDER_TASKn_DOCSTRING` markers means that requirement is entirely unmet and unfinished scaffolding shipped in committed test code. Fill each with the classification and reason per the plan (RED for Test 2; INAPPLICABLE-with-reason for Tests 3–5), using prose that names no phase/note identifier ("the async conversion", "the torn-tree isolation contract"), consistent with the module header that was correctly rewritten.

---

### Observations (non-blocking)

- **Test 2 is a deliberately failing (red) test.** Both threads reach the `clone` gate, the `Barrier(2)` releases both, both dispatch `git clone --mirror`, so `clone_dispatches == 2` and `assert clone_dispatches == 1` fails today by design (the "red-only by construction" scenario the spec sanctions; 20.2.2 relaxes the gate). This is intended, but note the branch's `make test` now contains one expected-failing test — surface it so CI/reviewers do not read the red as a regression. (Once Finding 1 is fixed, Tests 3/4/5 should pass; only Test 2 stays red.)
- **Test 3 shares Test 4's prune-vs-add exposure.** Its concurrent section releases `ensure`'s `fetch` and `tree`'s `worktree add` together, after which `ensure` runs `git worktree prune` concurrently with the in-flight `worktree add` — the same overlap Test 4 pins. The mid-run consistency assertion `path.exists() == (str(path) in _porcelain())` (line 136) will catch a torn state if the prune reaps the half-created worktree. That is the invariant being pinned and is acceptable, but it belongs in the (currently missing) docstring so the observed status is on record.

---

Findings must be resolved before REVIEW_PASS. Finding 1 (indefinite hang in two of the four scenarios) is the blocker; Finding 2 (placeholder docstrings) leaves the task's stated deliverable unmet.
