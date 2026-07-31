# Code Review (re-review) — 20.2.2 Give `RepoMirror` an async boundary

**Plan:** `.ai-factory/plans/11-20-2-2-give-repomirror-an-async-boundary.md`
**Prior review:** `.ai-factory/reviews/11-20-2-2-give-repomirror-an-async-boundary-review-1.md`
**Scope:** re-verified the prior review's items against current file contents, then re-ran the full review over `git diff HEAD`.
**Verification:** re-ran the non-DB affected suites (`tests/github`, `tests/versioning`, `tests/graph/test_coordination_seeder.py`, `tests/delivery/test_release_delivery.py`, `tests/knowledge/test_knowledge_sync.py`, `tests/knowledge/test_bootstrap.py`) → **140 passed** (incl. the full forced-interleaving concurrency contract).

## State since review-1

Review-1's verdict was **"No correctness, security, or concurrency defects found."** It raised **no blocking findings** — only two items explicitly labelled *"Non-blocking observations (optional future hardening — no change required)."* The source is unchanged since that pass: `git diff HEAD --stat` is byte-for-byte identical (`src/github/mirror.py` still `129 +++---`, every caller/test identical), and the only new working-tree entry is review-1.md itself. I re-read `src/github/mirror.py` in full and re-inspected the caller diffs rather than trusting session memory.

## Per-item verdicts (from review-1's two observations)

### Observation 1 — `asyncio.Lock` implicitly binds to the event loop that first uses it

**Verdict: Not fixed — and no fix was required (explicitly non-blocking).** Current content, `src/github/mirror.py:69` and `:74-84`:

```python
        self._ensure_locks: dict[str, asyncio.Lock] = {}
```
```python
    def _ensure_lock(self, repo: str) -> asyncio.Lock:
        """Lazily creates and returns `repo`'s serialization lock. Called
        only from synchronous code with no `await` in between the lookup and
        the insert, so two coroutines racing to create the same repo's lock
        can never both win — plain dict access on the event-loop thread is
        itself atomic with respect to other coroutines."""
        lock = self._ensure_locks.get(repo)
        if lock is None:
            lock = asyncio.Lock()
            self._ensure_locks[repo] = lock
        return lock
```

Unchanged from review-1. As stated then, this is a latent fragility only if a single `RepoMirror` instance were driven across two event loops; no current path does that (composition roots build the mirror inside the one loop that uses it; scripts use a single `asyncio.run`; test fixtures are function-scoped). Confirmed still not a defect.

### Observation 2 — `_ensure_locks` grows one entry per repo, never evicted

**Verdict: Not fixed — and no fix was required (explicitly non-blocking).** Current content, `src/github/mirror.py:69` (quoted above) plus its only insert site at `:83`. Unchanged. For Herald's bounded served-repo set this is negligible, exactly as noted before.

Neither item was a required change, so "not fixed" here means "correctly left as-is," not an outstanding defect.

## Full re-review — new issues

Re-read `src/github/mirror.py` end to end and re-inspected every caller diff (`src/delivery/service.py`, `src/versioning/versioner.py`, `src/main.py`, `src/knowledge/sync.py`, `src/graph/coordination.py`, `src/ingestion/writer.py`, `src/knowledge/bootstrap.py`, `src/episodic/backfill.py`, `src/changelog/report.py`, the three scripts) and the converted test fakes. Everything verified in review-1 still holds:

- Single owned offload (`_to_thread`, `:255`); `_reclaim_finished_worktrees` is `async` and awaited (`:210`, `:221`, called at `:165`); per-repo `asyncio.Lock` serializes `ensure` (`:146`) while `tree` takes no lock and holds nothing across `yield` (`:200-208`); credential env + `check/capture_output` preserved verbatim (`:238-253`); `resolve_canonical_ref` and `Versioner.next`/`_next_staging` are `async` with the only staging path awaiting `default_branch`.
- Every production shelling call is `await`ed / `async with`; ordering (`ensure` before `tree`/`default_branch`) preserved in each coroutine.
- Test suite green (140 passed), including the four pinned concurrency scenarios and both torn-tree tests.

No new correctness, security, race-condition, or type issues found.

REVIEW_PASS
