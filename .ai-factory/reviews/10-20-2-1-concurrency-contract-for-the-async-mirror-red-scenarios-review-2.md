## Re-review — 20.2.1 Concurrency contract for the async mirror (red scenarios)

Re-read `tests/github/conftest.py` and `tests/github/test_mirror_isolation.py` in full (with `src/github/mirror.py` as ground truth). Verdicts on the two prior findings, then a fresh full pass.

---

### Finding 1 (CRITICAL, prior review) — Tests 3 and 4 hang at their post-concurrency cleanup `ensure`

**Verdict: Fixed.**

A `clear_gates()` method was added to `GatedRunner` and is now called before each single-threaded cleanup `ensure`, so the solo call no longer re-trips a two-party `Barrier` gate.

- `tests/github/conftest.py:128-135`:
  ```python
  def clear_gates(self) -> None:
      """Drops every registered gate. A test calls this once its forced
      interleaving is over, before it drives the mirror any further on a
      single thread — otherwise a later solo call would hit a gate whose
      `release` is a multi-party `Barrier` and block forever waiting for a
      second party that will never arrive.
      """
      self._gates.clear()
  ```
- Test 3 (`test_finished_worktree_bookkeeping_stays_consistent_under_thread_concurrency`), `tests/github/test_mirror_isolation.py:202-203`:
  ```python
      runner.clear_gates()
      mirror.ensure(REPO, ORG_ID)
  ```
- Test 4 (`test_worktree_prune_does_not_race_a_worktree_being_created`), `tests/github/test_mirror_isolation.py:271-272`:
  ```python
      runner.clear_gates()
      mirror.ensure(REPO, ORG_ID)  # flush deferred reclamation, keep the mirror clean
  ```

`clear_gates()` is invoked only after every worker thread has joined (`future.result()` has returned), so there is no concurrent `__call__` iterating `self._gates` while it is cleared — the mutation is race-free. Test 5's final solo `ensure` (line 334) was never affected: its `fetch` gate is backed by a `threading.Event` that the test `.set()`s at line 319, so the solo call passes straight through. All three priming `ensure`s (lines 166, 236, 301) run before their gates are registered. No remaining single-threaded path can re-enter a multi-party gate.

### Finding 2 (BLOCKER, prior review) — all four scenario docstrings were unfilled placeholders

**Verdict: Fixed.**

Every `PLACEHOLDER_TASKn_DOCSTRING` marker is gone (confirmed by search); each scenario now carries prose that states its observed RED/INAPPLICABLE classification and the reason, using no phase/note identifier.

- Test 2, `test_mirror_isolation.py:87-89`: *"Observed status: RED against today's synchronous mirror under real threads -- both threads take the clone branch and a clone is dispatched twice, so the assertion that it is dispatched exactly once fails."*
- Test 3, `:155-158`: *"Observed status: INAPPLICABLE against today's synchronous mirror -- passes under real threads because the existing lock around the append and the snapshot-clear already serializes them…"*
- Test 4, `:223-226`: *"Observed status: INAPPLICABLE against today's synchronous mirror -- the forced overlap does not reap or corrupt the worktree; the created worktree survives with its exact pinned content."*
- Test 5, `:287-290`: *"Observed status: INAPPLICABLE against today's synchronous mirror -- the open tree is undisturbed both during and after the overlapping `ensure`."*

The identifier-free convention holds: the docstrings say "the async conversion" / "a later concurrent mirror" / "the existing torn-tree isolation contract" rather than `20.2.2` / `3.1.1`.

---

### Fresh full pass — new issues

Re-examined the harness and all six tests for deadlocks, races, and correctness:

- **`GatedRunner` gate matching** (`conftest.py:137-149`) — records argv under `self._lock`, matches `command[:len(key)] == key`, sets `reached`, waits on `release`. Correctly distinguishes `clone` / `fetch` / `("worktree","add")` / `("worktree","prune")` from `("worktree","remove")`. No gate matches a command it shouldn't.
- **Test 3 concurrent section** — the barrier is tripped exactly once (E's `fetch` + T's `worktree add`); E's later `worktree remove`/`worktree prune` match no gate, so there is no second barrier entry mid-run. Reclamation's snapshot-clear and `tree`'s append remain lock-serialized; E can only ever remove a scratch that `tree` finished registering (post-`add`), so no use-after-remove. Consistent under either lock-arbitration order.
- **Test 4 concurrent section** — barrier tripped once (T's `add` + E's `prune`); E's reclamation list is empty at that point (no closed tree before the run), so E dispatches no `worktree remove` and never enters a second gate. No deadlock.
- **Test 2** — `Barrier(2)` on `clone` forces both threads past the `exists()==False` check to the clone subprocess, both dispatch `clone`, the loser's `CalledProcessError` is swallowed, and the count assertion is evaluated on the shared runner after join. Deterministic, and does not hang (both parties reach the barrier; the winner's follow-on `worktree prune` is ungated).
- No shared mutable state across tests; each uses its own `tmp_path`, `GatedRunner`, and mirror, so the suite is parallel-safe.

**Non-blocking notes (intended behavior, not defects):**
- Test 2 is a **deliberately failing (red) test** — `assert clone_dispatches == 1` fails today because both threads clone. This is exactly the spec's "red-only by construction" scenario and is now documented in the test's own docstring; the branch's `make test` therefore carries one intentional failure until the async-conversion follow-up relaxes the gate. Surfaced here so the red is not misread as a regression.
- Test 3's mid-run consistency check `assert path.exists() == (str(path) in _porcelain())` (line 194) shares the prune-vs-`add` exposure that Test 4 pins deterministically; a torn state on some platform would surface here. The docstring (lines 148-153) explicitly acknowledges this, and the observed status is INAPPLICABLE. Acceptable per the scenario's design.

Both prior findings are fixed and no new defects were found.

REVIEW_PASS
