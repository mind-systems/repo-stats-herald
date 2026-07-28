# Plan: 23.1 — Read git paths in the encoding Python expects

## Context
`GitCommitCollector.collect` runs its `git log --numstat` with git's default path quoting, so non-ASCII filenames land in `Commit.changed_files` as double-quoted, octal-escaped strings that never equal a real path. Disable the quoting on that one invocation, matching the sibling `changed_paths` method.

## Settings
- Testing: no
- Logging: minimal
- Docs: no

## Tasks

### Phase 1: Normalize the log invocation

- [x] **Task 1: Disable path quoting on the `_collect_commits` git log call**
  Files: `src/commits/collector.py`
  In `GitCommitCollector._collect_commits` (the `git log --numstat --shortstat` invocation, currently lines ~308–324), add `-c core.quotepath=false` to the argument list immediately after `self._git_bin`, exactly as the sibling `changed_paths` method already does (its `-c`, `core.quotepath=false` pair sits before `-C`). This keeps non-ASCII path bytes literal so collected `changed_files` entries equal real paths and match what `changed_paths` reports.
  Guards (from the task spec):
  - Change **only** the invocation. Do not touch `_parse_tail`, `_parse_record`, `_NUMSTAT_RE`, `_SHORTSTAT_RE`, or any record framing / field splitting.
  - Do not add any unquoting or escape-handling logic — paths git quotes for an embedded newline or quote are explicitly out of scope.
  - An all-ASCII repository must produce byte-identical output to today.
  - Do not edit `changed_paths`; it is already correct.
  - Note: 23.2 touches this same invocation next; keep the edit minimal so it lands cleanly after this one.
