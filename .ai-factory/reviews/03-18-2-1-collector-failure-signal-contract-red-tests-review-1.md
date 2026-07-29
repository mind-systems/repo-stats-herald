# Code Review — 18.2.1 Collector failure-signal contract (red tests)

**Files reviewed (in full):** `src/commits/collector.py`, `tests/commits/test_collector.py`
**Also checked:** `src/versioning/versioner.py` (consumer, must stay untouched), `tests/commits/conftest.py` (fixtures), plan + spec.
**Risk level:** 🟢 Low

## Scope of the change
Two files touched, both in the diff:
- `src/commits/collector.py` — one additive module-level `class CommitCollectionError(Exception)` with a one-line docstring, placed after `EMPTY_TREE_SHA` and before `GitCommitCollector`.
- `tests/commits/test_collector.py` — import of `CommitCollectionError`; clarifying comments on the two back-merge cases; one new case `test_new_commits_raises_on_git_failure`.

This is a deliberately-red-test task: the new failure case is expected to FAIL against today's body, and that redness is the deliverable.

## Verification performed

- **Test run.** `uv run pytest tests/commits/test_collector.py` → `1 failed, 14 passed`. The only failure is `test_new_commits_raises_on_git_failure` with `Failed: DID NOT RAISE CommitCollectionError` — exactly the intended red. All three restated back-merge/staging-unique cases and every other case pass unchanged.

- **Redness is for the right reason, and will go green under the intended fix.** I ran the exact invocation the method issues — `git rev-list --no-merges --end-of-options <sha>..<sha> ^no-such-branch` — against a fresh one-commit repo: it prints `fatal: bad revision '^no-such-branch'` and exits `128`. So today's `if result.returncode != 0: return ()` swallows a genuine non-zero exit into an empty tuple (no raise → red now), and once 18.2.2 wires a raise on non-zero exit this same invocation will raise → green. The red test is therefore valid: it cannot pass by accident today and is guaranteed to be satisfiable by the intended implementation, not a dead red.

- **Guards honored.** `new_commits`'s body and docstring are unchanged (docstring still states the no-raise contract, matching the still-unchanged body — prose and code do not disagree at this step). `Versioner._next_staging` is not in the diff and still reads the old shape. The three restated cases keep their git setup and assertions (`()` / `(staging_sha,)`); only comments were added, so back-merge detection is narrowed by nothing.

- **Additive, no collision.** `CommitCollectionError` is a new name; the change adds a class and cannot break existing imports. The test import `from src.commits.collector import ... CommitCollectionError ...` resolves against the module-level definition.

- **No lint gate to break.** `pyproject.toml` configures no ruff/line-length rule and ruff is not installed; the project's gate is `make test` (pytest). The 148-char one-line docstring is not a CI concern.

## Findings
None.

REVIEW_PASS
