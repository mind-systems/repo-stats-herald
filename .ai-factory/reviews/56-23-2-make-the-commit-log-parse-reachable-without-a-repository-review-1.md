# Code Review: 23.2 — Make the commit-log parse reachable without a repository

## Scope
Single production file changed: `src/commits/collector.py`. The remaining staged changes are planning artifacts (`.ai-factory/plans/...`, `.ai-factory/plan-reviews/...`). Reviewed the full modified file, not just the diff.

## What changed
- `_collect_commits` (which both shelled out to `git log` **and** parsed the result) is split into two:
  - `parse_log(self, log_text, repo, branch) -> CommitContext` — the record-splitting/parsing loop, operating on passed-in text.
  - `_run_log(self, repo_path, rev_range) -> str` — the `subprocess.run` invocation, returning raw stdout.
- `collect` now resolves the branch, calls `_run_log`, and delegates to `parse_log`.

## Correctness verification

- **Parse loop moved verbatim.** The loop in `parse_log` (lines 313–320) is identical to the former `_collect_commits` body — same `_RECORD_SEP` split, same `if not record.strip()` skip, same `_parse_record` call, same `tuple(commits)`. Only the source changed from `result.stdout` to `log_text`. `_parse_record` and `_parse_tail` are untouched, so record framing, field separation, numstat/shortstat reading, and subject/body joining (including their pre-existing quirks) are preserved exactly.
- **`_run_log` preserves the invocation.** The `subprocess.run` argument list is byte-for-byte the same, including the `-c core.quotepath=false` flag landed by 23.1, `--end-of-options`, `--numstat --shortstat`, the `_PRETTY_FORMAT`, `text=True`, and `check=True`. Fail-loud-on-bad-range behaviour is retained.
- **`collect` behaviour-identical.** Previously returned `CommitContext(repo=repo_path, branch=branch, commits=…)`; now returns `parse_log(log_text, repo=repo_path, branch=branch)`, which constructs the same context with the same `repo` (`repo_path`), same `branch` (unchanged `_current_branch`), and the same commit tuple. Signature and return type unchanged.
- **Guard — parse-over-text only.** `parse_log` takes no repo *path*, never calls `subprocess`, and never touches the filesystem; `repo`/`branch` are written straight into the context as labels. The seam is exactly the pure-text parse the spec requires, making record-separator-in-subject / brace-rename / large-stat cases reachable by value.
- **No dangling references.** The only references to `_collect_commits` are in historical planning docs; no code calls it. No collision with the new `_run_log` name. Every runtime caller reaches the parse through `collect` (unchanged) — nothing else in the tree calls the renamed helper.
- **Untouched contracts.** `new_commits` and the empty-vs-failed range distinction (owned by 18.2.1/18.2.2) are not modified. No other collector method changed.

## Runtime risk assessment
No new imports, no signature changes to public methods, no I/O reordering. `parse_log` on empty/blank text yields an empty commit tuple (leading `_RECORD_SEP` element and blank records are skipped), matching prior behaviour. No migration, type-mismatch, or concurrency concern — the method is pure over its inputs.

## Findings
None.

REVIEW_PASS
