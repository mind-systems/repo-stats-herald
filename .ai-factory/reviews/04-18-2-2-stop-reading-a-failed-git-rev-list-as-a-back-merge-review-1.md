## Code Review — 18.2.2 Stop reading a failed `git rev-list` as a back-merge

**Files reviewed in full:** `src/commits/collector.py`, `src/versioning/versioner.py`, `tests/commits/test_collector.py`. Diff via `git diff HEAD`; production callers of `new_commits` grepped repo-wide.
**Risk level:** 🟢 Low — two owned classes, no boundary/DI/schema change, behavior unchanged for every path except the previously-silent `git` failure.

### What changed
- `GitCommitCollector.new_commits` now `raise`s `CommitCollectionError` on a non-zero exit instead of returning `()`; docstring rewritten to state the new contract.
- `Versioner._next_staging` inline comment updated; no logic change — the exception propagates out of `_next_staging`/`Versioner.next` automatically.

### Correctness
- **Failure signal is wired correctly.** `subprocess.run(..., capture_output=True, text=True, check=False)` means `result.stderr` is a populated `str` on the failure path, so `result.stderr.strip()` is safe and the message is informative. `CommitCollectionError` is imported/defined in the same module (collector.py:29). No `NameError` risk.
- **No secret leak.** The exception message carries `before`, `after`, `exclude_ref`, and git's stderr — SHAs, a branch name, and git diagnostics. `repo_path` is not interpolated, matching the plan's guard; nothing credential-bearing reaches the string.
- **Empty-range path preserved.** A zero exit still returns the parsed non-merge SHAs, so a genuine fast-forward or merge-commit back-merge still yields `()` and `Versioner.next` still returns `None`. Verified by `test_new_commits_empty_for_fast_forward_back_merge`, `test_new_commits_empty_for_merge_commit_back_merge`, and `test_new_commits_returns_staging_unique_non_merge_commits` — all green.
- **Failure now distinguishable.** `test_new_commits_raises_on_git_failure` (unresolvable `exclude_ref` → `git rev-list ^no-such-branch` non-zero) asserts `CommitCollectionError`; green after the change, was red before. The conflation the task targets is closed.
- **Single call site.** `new_commits` is consumed only at `versioner.py:122`; grep finds no other production caller, so the contract change is fully contained. The `if not self._collector.new_commits(...)` guard never evaluates on failure — the raise short-circuits it — so the `return None` branch is reached only for a real empty range, exactly as annotated.
- **Docstring/prose match code.** The stale "Read-only and no-raise: an empty tuple on non-zero exit" line is gone from `new_commits`; the `_next_staging` comment now states a `git` failure raises and never lands in the back-merge branch. No contradicting prose remains in either method.

### Tests
`tests/commits/test_collector.py` (15 passed) and `tests/versioning` (8 passed) both green. No new tests were needed — 18.2.1 already authored the failure case; this task turns it green.

### Notes (non-blocking, out of scope)
- Consistent with the plan-review's deferred observation: `Versioner.next` is invoked inside the ingestion background release/delivery fan-out (`src/ingestion/router.py`) with no surrounding try/except in this task's boundary. Raising there is the *intended* outcome of 18.2.2 (fail loud, not silent `None`); whether the raised `CommitCollectionError` becomes an operator-visible log line versus a swallowed background-task error belongs to whatever phase owns the fan-out error contract, not here.

REVIEW_PASS
