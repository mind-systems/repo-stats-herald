# Code Review: 18.1 — Normalize a branch-creation `before` at parse time

**Scope:** `src/ingestion/router.py` (only code file changed; the rest of the diff is planning artifacts).

## What changed
`_parse_push_event` now maps an all-zero `before` SHA to `EMPTY_TREE_SHA` before building `PushEvent`:
- Added `from src.commits.collector import EMPTY_TREE_SHA`.
- Added module constant `_CREATION_BEFORE_SHA = "0" * 40`.
- Normalized `before = EMPTY_TREE_SHA if payload["before"] == _CREATION_BEFORE_SHA else payload["before"]`; `after` and every other field untouched.

## Correctness
- **Matches spec 53 and the plan exactly.** Only the literal 40-zero SHA is rewritten; any other value — including short or malformed — flows through verbatim, so normal (non-creation) pushes are unaffected.
- **Type safe.** `PushEvent.before` is a plain `str`; both branches of the conditional yield a `str`. No serialization impact (`jsonable_encoder(event)` still emits a valid SHA string).
- **Single construction site.** `PushEvent` is built only at `router.py:143`, so no other parse path needs the same normalization.
- **`after` guard honored.** Deletion's symmetric all-zero `after` is intentionally out of scope (spec 53 guards `after` as untouched; flagged for Phase 19 in the plan-review).
- **No versioner change.** `src/versioning/versioner.py` is not touched; it keeps operating over resolved SHAs. The empty-tree SHA is a git-valid `before` (`git rev-list <EMPTY_TREE_SHA>..<after>` exits 0), which is precisely what unblocks the first-ever staging push from being mis-read as a back-merge.

## Security
No regression. The comparison is an exact-equality guard against a fixed literal; no user-influenced value reaches a shell (downstream git calls already use `--end-of-options`). An attacker cannot use this to inject a different revision — a non-matching `before` is passed through exactly as before this change.

## Runtime / breakage
No schema, migration, or async concern. `EMPTY_TREE_SHA` is a module-level constant with no import cycle risk (`ingestion` already depends on `commits` via `GitCommitCollector` in sibling modules).

REVIEW_PASS
