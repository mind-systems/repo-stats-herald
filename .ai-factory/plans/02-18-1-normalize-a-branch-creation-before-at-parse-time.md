# Plan: 18.1 — Normalize a branch-creation `before` at parse time

## Context
Rewrite GitHub's all-zero branch-creation `before` SHA to `EMPTY_TREE_SHA` at the ingestion boundary so the first-ever `staging` push cuts `v0.1.0-rc` instead of being silently read as a back-merge and skipped.

## Settings
- Testing: no
- Logging: minimal
- Docs: no

## Tasks

### Phase 1: Normalize the sentinel at parse time

- [x] **Task 1: Map the all-zero `before` to `EMPTY_TREE_SHA` in `_parse_push_event`**
  Files: `src/ingestion/router.py`
  Import `EMPTY_TREE_SHA` from `src/commits/collector.py` alongside the existing `src/ingestion` imports. In `_parse_push_event`, before constructing `PushEvent`, define a module-level constant for the literal all-zero SHA (40 `0` chars, e.g. `_CREATION_BEFORE_SHA = "0" * 40`) and normalize: `before = EMPTY_TREE_SHA if payload["before"] == _CREATION_BEFORE_SHA else payload["before"]`, then pass `before=before` into `PushEvent`. Leave `after=payload["after"]` and every other field untouched. Only the exact all-zero value is rewritten — any other `before`, including short or malformed ones, passes through verbatim. Do not touch `src/versioning/versioner.py`: it keeps operating purely over resolved SHAs with no zero-SHA branch.
