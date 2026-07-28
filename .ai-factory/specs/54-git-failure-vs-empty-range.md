# 18.2.2 — Stop reading a failed `git rev-list` as a back-merge

**Phase:** 18 — Silent release loss & unwired promises. Independent of 18.1. Depends on the preceding contract task, which owns the failure-signal declaration and the red tests that pin it.

## Current state

`GitCommitCollector.new_commits` documents itself as read-only and no-raise: it returns an empty tuple both for a genuine empty range and for any non-zero `git` exit. Its only production caller, `Versioner._next_staging`, treats an empty result as proof of a back-merge and returns `None`. A corrupt local mirror, an unresolvable `exclude_ref`, or any other `git` failure at that call therefore suppresses a `staging` release with no error, no log line distinguishing it from a real back-merge, and no way for an operator to tell the two apart after the fact. By this task, the failure signal is already declared on the collector's public surface and pinned by red tests; those tests are red until this task lands.

## Change

Turn the preceding task's red tests green: `new_commits` actually raises or returns the declared signal on a non-zero exit, and `_next_staging` lets that failure propagate as an error instead of reading it as a back-merge.

## Files & types

- edit `src/commits/collector.py` (`GitCommitCollector.new_commits`)
- edit `src/versioning/versioner.py` (`Versioner._next_staging`)

## Guards

- A genuine empty range (a real back-merge, fast-forward or via a merge commit) still resolves to "back-merge," and `Versioner.next` still returns `None` for it — this task changes no observable behavior for that path.
- The docstring on `new_commits` is rewritten to state the new contract exactly; it never describes behavior the code no longer has.
- No caller of `new_commits` exists outside `Versioner`, so the contract change has one call site to update, not several.

## Verification

- A `git` failure at the `new_commits` call (simulated: an invalid `exclude_ref` or an unreadable mirror path) surfaces as an error out of `Versioner.next` rather than a silent `None`.
- A fast-forward back-merge still yields no bump.
- A merge-commit back-merge still yields no bump.
