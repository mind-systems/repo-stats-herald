## Code Review Summary

**Files Reviewed:** 1 plan (`04-18-2-2-...`), against `src/commits/collector.py`, `src/versioning/versioner.py`, `tests/commits/test_collector.py`, spec `54-git-failure-vs-empty-range.md`, and the `18.2.2` roadmap line.
**Risk Level:** 🟢 Low

### Context Gates
- **Roadmap (`ROADMAP.md`):** PASS. Line `18.2.2` is `[ ]` and points to `.ai-factory/specs/54-git-failure-vs-empty-range.md`; the plan's title, scope, and guards match the contract line and the spec's Change/Guards/Verification exactly (raise on non-zero exit, propagate at `_next_staging`, rewrite the docstring, keep genuine-empty-range → `None`).
- **Architecture (`.ai-factory/ARCHITECTURE.md` / project CLAUDE.md):** PASS. The change stays inside two owned classes — the git-command detail stays inside `GitCommitCollector`, the staging seam stays inside `Versioner`. No composition-root or DI boundary is touched; no feature-to-feature dependency introduced.
- **Rules (`.ai-factory/RULES.md`):** PASS. File is intentionally empty of counter-defaults; nothing to enforce. No `skill-context/aif-review/SKILL.md` present.

### Critical Issues
None.

### Verification against ground truth
- **Body edit is precise.** `new_commits` (collector.py:263–265) currently holds exactly the `if result.returncode != 0: return ()` branch the plan targets; `capture_output=True` means `result.stderr` is available to embed in the message. Task 1 is implementable as written.
- **`CommitCollectionError` already exists** (collector.py:29–30, from 18.2.1) — the plan correctly treats it as declared, not to be re-added.
- **Red test will turn green.** `tests/commits/test_collector.py::test_new_commits_raises_on_git_failure` (line 171) drives `new_commits(..., "no-such-branch")`, whose `git rev-list ^no-such-branch` exits non-zero → the new `raise` satisfies `pytest.raises(CommitCollectionError)`. The three back-merge/staging-unique cases assert `()` / `(staging_sha,)` on a zero exit and stay green, matching the plan's claim. "Testing: no" is correct — the cases already exist.
- **Single call site confirmed.** `new_commits` is consumed only at `versioner.py:122`; grep finds no other caller, so the contract change has one seam to update, matching spec guard and Task 3.
- **Propagation is automatic and correct.** With `new_commits` raising, the `if not self._collector.new_commits(...)` guard at versioner.py:122 never evaluates on failure — the exception propagates out of `_next_staging`/`Versioner.next`. The `return None` branch is then reached only for a genuine empty range, exactly as Task 3 states. No new zero-SHA/error branch is needed.

### Positive Notes
- Task decomposition mirrors the spec's own structure (collector body + docstring, then the staging seam) and each task names the concrete file and the exact line-level change, leaving no guessing for the implementer.
- The plan explicitly preserves the observable back-merge behavior (`Versioner.next` still returns `None` for a real empty range) and calls out that no try/except is added — matching the spec's "changes no observable behavior for that path" guard.
- Minor, non-blocking: Task 1 writes "the failing `rev_range`/`exclude_ref`" — `new_commits` has no `rev_range` parameter; it is clear shorthand for the `before..after` range built from the `before`/`after` args, and any implementer resolves it trivially.

## Deferred observations
- Affects: ingestion fan-out (`src/ingestion/router.py:69`, outside this task's `collector.py`/`versioner.py` boundary) — `versioner.next(...)` is called inside the background release/delivery task with no surrounding try/except. The spec's Verification deliberately stops at "surfaces as an error out of `Versioner.next` rather than a silent `None`," so raising here is the intended outcome of this task; whether that raised `CommitCollectionError` becomes an operator-visible log line (rather than a background-task crash a runner might swallow) depends on the fan-out's error handling, which this task does not touch. Worth confirming in whatever phase owns the ingestion background-task error contract.

PLAN_REVIEW_PASS
