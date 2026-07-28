# 18.1 — Normalize a branch-creation `before` at parse time

**Phase:** 18 — Silent release loss & unwired promises. Independent of 18.2 and 18.3 — normalizes the sentinel at the ingestion boundary, before either downstream task's surface is reached. No new dependency; reuses the existing `EMPTY_TREE_SHA` constant.

## Current state

On branch creation GitHub sends `before` as the all-zero SHA (`0000000000000000000000000000000000000000`). `_parse_push_event` in `src/ingestion/router.py` copies `payload["before"]` verbatim into `PushEvent`, so the sentinel travels through the whole pipeline unchanged. When a creation push lands on `staging`, `Versioner._next_staging` calls `GitCommitCollector.new_commits`, whose underlying `git rev-list 000..after` exits non-zero against the all-zero SHA; `new_commits` returns an empty tuple, and the back-merge guard reads that emptiness as "no staging-unique work" and returns `None` — the first-ever `staging` push for a new branch is silently skipped instead of cutting `v0.1.0-rc`.

## Change

In `_parse_push_event`, rewrite an all-zero `before` to `EMPTY_TREE_SHA` before constructing `PushEvent`. This is the identical sentinel `SinceDeployWindow` and `Report` already use to mean "no real boundary exists yet," so every downstream consumer of `PushEvent.before` — the versioner included — receives a real, well-formed SHA it can already run `git` operations against. Normalization happens once, at the boundary where the GitHub-specific convention is understood; nothing downstream needs to know the sentinel ever existed.

## Files & types

- edit `src/ingestion/router.py` (`_parse_push_event`)
- import `EMPTY_TREE_SHA` from `src/commits/collector.py`

## Guards

- Only the literal all-zero SHA is rewritten; any other `before` value, including a short or malformed one, passes through unchanged.
- `after` is never touched by this normalization.
- `Versioner.next` gains no zero-SHA branch or special case — it keeps being specified purely over resolved SHAs, so this task changes no line in `src/versioning/versioner.py`.
- No other field of `PushEvent`, and no other consumer of `payload["before"]`, changes behavior for a normal (non-creation) push.

## Verification

- A branch-creation push (`before` = all-zero) to `staging` produces a version and cuts `v0.1.0-rc` rather than returning `None`.
- An ordinary push with a real `before` SHA is unaffected — same version outcome as before this change.
- A genuine back-merge push (a real `before`, no staging-unique commits) still yields no bump.
