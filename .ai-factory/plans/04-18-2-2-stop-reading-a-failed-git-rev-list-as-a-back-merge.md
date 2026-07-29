# Plan: 18.2.2 — Stop reading a failed `git rev-list` as a back-merge

## Context
Make `GitCommitCollector.new_commits` raise on a non-zero `git` exit instead of returning an empty tuple, so `Versioner._next_staging` no longer mistakes a `git` failure (corrupt mirror, unresolvable `exclude_ref`) for a legitimate back-merge and silently suppresses a staging release.

## Settings
- Testing: no
- Logging: minimal
- Docs: no

## Tasks

### Phase 1: Wire the failure signal into the collector

- [x] **Task 1: Raise `CommitCollectionError` on a non-zero `git` exit in `new_commits`**
  Files: `src/commits/collector.py`
  `CommitCollectionError` is already declared (from 18.2.1) but `new_commits`'s body still swallows failure. In `GitCommitCollector.new_commits`, replace the `if result.returncode != 0: return ()` branch with `raise CommitCollectionError(...)`. Include the failing `rev_range`/`exclude_ref` and git's captured `stderr` in the message so an operator can distinguish this from a genuine empty range after the fact; do not include `repo_path` secrets beyond what other errors already expose. A zero exit still returns the parsed non-merge SHAs unchanged, so a genuine empty range (fast-forward or merge-commit back-merge with no staging-unique work) still yields `()`. This turns the already-written `test_new_commits_raises_on_git_failure` case green and keeps the two back-merge cases and the staging-unique case passing.

- [x] **Task 2: Rewrite the `new_commits` docstring to state the new contract** (part of Task 1's edit)
  Files: `src/commits/collector.py`
  The current docstring says "Read-only and no-raise: an empty tuple on non-zero exit." Rewrite that sentence so the stated contract matches the new body: an empty tuple means only a genuine empty range (a back-merge with no staging-unique non-merge work); a non-zero `git` exit raises `CommitCollectionError`. Keep the rest of the docstring (the `--no-merges`/`^exclude_ref`/`--end-of-options` explanation) intact. Do not leave the stale "no-raise" wording anywhere in the method.

### Phase 2: Let the failure propagate at the staging seam

- [x] **Task 3: Confirm and annotate failure propagation in `_next_staging`** (depends on Task 1)
  Files: `src/versioning/versioner.py`
  With `new_commits` now raising, a `git` failure propagates out of `_next_staging` and `Versioner.next` automatically — no try/except is added and no failure is caught or converted back into `None`. Keep the `if not self._collector.new_commits(...): return None` structure: after this change the `None` branch is reached only for a genuine empty range (a real back-merge), which is the intended unchanged behavior. Update the inline comment on that branch to state that only a genuine empty range reaches here now — a `git` failure raises `CommitCollectionError` and never lands in the back-merge path — so prose and code agree. Do not add any new zero-SHA or error-handling branch; `Versioner.next` still returns `None` for a real back-merge exactly as today.
