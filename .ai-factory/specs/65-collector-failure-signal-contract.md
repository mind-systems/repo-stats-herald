# 18.2.1 — Collector failure-signal contract (red tests)

**Phase:** 18 — Silent release loss & unwired promises. Independent of 18.1. Precedes 18.2.2, which turns the red tests this task pins into green behavior.

## Current state

`new_commits` documents itself as read-only and no-raise, returning an empty tuple on any non-zero exit. Its only production consumer treats an empty result as proof of a back-merge and skips the release. `tests/commits/test_collector.py` holds three cases — a fast-forward back-merge, a merge-commit back-merge, and staging-unique commits — and none of them exercises a failing `git` invocation, so the conflation between a genuine empty range and a failed command is entirely uncovered.

## Change

Declare the failure signal. The fork is a dedicated exception type versus a sentinel return versus an optional-wrapped result, and this task's job is to settle it and express it in the collector's public surface without yet changing the method's body. Then write the tests that pin it: the three existing cases restated against the settled contract, plus a new case driving a genuine `git` failure and asserting the declared signal.

## Files & types

- edit `src/commits/collector.py` (declare the failure signal on `GitCommitCollector.new_commits`'s public surface)
- edit `tests/commits/test_collector.py` (restate the three existing `new_commits` cases against the settled contract; add a new case for a genuine `git` failure)

## Guards

- The declaration lands but `new_commits`'s body is unchanged, so the new failure case is red.
- The consumer is not touched in this task and still reads the old shape.
- The three restated cases must keep asserting the same behavior they assert today for a genuine empty range — this task narrows nothing about back-merge detection.
- The docstring on `new_commits` is NOT rewritten here — it still describes today's no-raise behavior, which is still what the body does. The impl task rewrites it at the moment the body changes to match, so prose and code never disagree.

## Verification

- The new failure case fails against today's implementation.
- The three back-merge and staging-unique cases pass unchanged in meaning.
- Nothing outside the collector and its test module is touched.
