# Plan: 23.2 — Make the commit-log parse reachable without a repository

## Context
Expose the commit-log parse (record framing, field splitting, numstat/shortstat reading) as a public entry point on `GitCommitCollector` that accepts raw log text plus repo/branch labels and returns the same `CommitContext`, so the parse can be exercised with a value instead of a real repository. Purely additive: `collect` keeps shelling out and delegates to the new entry point; no parsing rule changes.

## Settings
- Testing: no
- Logging: minimal
- Docs: no

## Tasks

### Phase 1: Extract the parse behind a public entry point

- [x] **Task 1: Add the public `parse_log` entry point and split the git invocation out of it**
  Files: `src/commits/collector.py`
  Add a public method to `GitCommitCollector` that takes the raw `git log` text plus the repository and branch labels and returns a `CommitContext` — this is the parse-over-text seam the task asks for:
  - Signature: `parse_log(self, log_text: str, repo: str, branch: str) -> CommitContext`.
  - Move the record-splitting loop that currently lives inside `_collect_commits` (lines splitting on `_RECORD_SEP`, skipping blank records, calling `self._parse_record`, collecting into a tuple) into `parse_log` **verbatim** — operating on the passed-in `log_text` instead of `result.stdout`. Return `CommitContext(repo=repo, branch=branch, commits=<parsed tuple>)`.
  - Leave `_parse_record` and `_parse_tail` exactly as they are; `parse_log` calls them unchanged. Do not alter the record framing, field separation, numstat/shortstat reading, or subject-and-body joining — current behaviour (including current defects) must be preserved exactly.
  - Reduce the private git-invocation helper (currently `_collect_commits`) to *only* shelling out and returning git's stdout text. Give it a name that reflects that it now yields raw text (e.g. rename `_collect_commits` → `_run_log` returning `str`), keeping the exact same `subprocess.run` call, arguments, `check=True`, and `core.quotepath=false` config. The helper must not parse.
  - Guard: `parse_log` is a parse over text only — it must not accept a repo *path*, shell out, or touch the filesystem. The `repo`/`branch` parameters are label strings written straight into the returned context, nothing more.

- [x] **Task 2: Delegate `collect` to the new seam** (depends on Task 1)
  Files: `src/commits/collector.py`
  Rewire `collect(self, repo_path, rev_range)` so it: resolves `branch` via `self._current_branch(repo_path)` (unchanged), obtains the raw log text from the private git-invocation helper (`self._run_log(repo_path, rev_range)`), and returns `self.parse_log(log_text, repo=repo_path, branch=branch)`.
  - `collect`'s signature, return type, and observable behaviour stay identical to today: same `repo` value (`repo_path`), same `branch`, same commit tuple. This is a refactor of the internals only.
  - Do not touch `new_commits` or the empty-versus-failed range distinction (owned by 18.2.1 / 18.2.2). Do not touch any other method on the collector.
