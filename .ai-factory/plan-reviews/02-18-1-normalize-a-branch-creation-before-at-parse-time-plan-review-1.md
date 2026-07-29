## Plan Review Summary

**Plan:** 18.1 — Normalize a branch-creation `before` at parse time
**Files Reviewed:** plan + `src/ingestion/router.py`, `src/commits/collector.py`, `src/versioning/versioner.py`, `src/ingestion/models.py`, `src/ingestion/writer.py`, `src/episodic/linked_change.py`; governing spec `.ai-factory/specs/53-creation-sha-normalization.md`; roadmap line 18.1
**Risk Level:** 🟢 Low

### Context Gates
- **Roadmap linkage — OK.** Plan's `# Plan:` heading matches ROADMAP.md line 18.1, which names `Spec: .ai-factory/specs/53-creation-sha-normalization.md`. Plan is verified against that spec, not just the roadmap line.
- **Governing spec — OK.** The plan conforms to spec 53 clause by clause: rewrite only the literal all-zero `before` to `EMPTY_TREE_SHA` at parse time; leave `after` untouched; add no zero-SHA branch to `Versioner`. The spec explicitly blesses the broad seam ("every downstream consumer of `PushEvent.before` — the versioner included — receives a real, well-formed SHA"), so the change is intentionally system-wide, not versioner-only.
- **Architecture — WARN (non-blocking).** `src/ingestion/router.py` will import the module-level constant `EMPTY_TREE_SHA` from `src/commits/collector.py`. ARCHITECTURE.md's dependency rule prefers cross-feature reuse via a public class injected through the constructor, not a bare imported symbol. However: (a) the governing spec explicitly directs this exact import; (b) precedent already exists — `src/ingestion/writer.py` and `src/versioning/versioner.py` both `from src.commits.collector import GitCommitCollector`, so `commits` already functions as shared git infrastructure; (c) importing the single canonical constant is DRY-correct versus duplicating the 40-char SHA literal in ingestion. Accept as a spec-sanctioned, precedented reuse.
- **Rules — OK.** No relevant `.ai-factory/RULES.md` constraint. No `.ai-factory/skill-context/aif-review/SKILL.md` present.

### Critical Issues
None. No missing migrations (no schema touched), no security regression (only the exact all-zero literal is rewritten; any other/malformed `before` passes through verbatim exactly as today, and downstream git calls already guard with `--end-of-options`), correct file paths, correct API usage.

### Verification performed
The plan's core assumption is that `EMPTY_TREE_SHA` is a git-valid `before` where the all-zero SHA is not. I confirmed this empirically against a scratch repo:
- `git rev-list --no-merges <EMPTY_TREE_SHA>..<after> ^<ref>` → exit 0, returns the branch-unique commits (the exact shape `GitCommitCollector.new_commits` runs). The all-zero form → `fatal: Invalid revision range`, exit 128 → `new_commits` returns `()` → back-merge guard → `None`. This is precisely the bug, and the fix resolves it.
- `git log <EMPTY_TREE_SHA>..<after>` → exit 0. This matters beyond the versioner: `EpisodicWriter.write` (`src/ingestion/writer.py`) also consumes `push.before` via `LinkedChangeResolver.resolve` → `GitCommitCollector.collect` → `_run_log`, which uses `check=True` and would **raise** on the all-zero SHA. Under the fix it walks cleanly from the empty tree. The spec's "every downstream consumer" wording covers this; the plan text frames the change only around the versioner but the broader seam is correct and spec-blessed.
- `git show <EMPTY_TREE_SHA>:<path>` → exit 128 (path absent in empty tree), same as the all-zero SHA, so `LinkedChangeResolver._read_roadmap_at` still returns `None` for the `before` roadmap version — no behavior change there. Correct: a first push's completed-task set is computed against an empty roadmap, matching the collector's own "root commit's before is the empty-tree SHA" model.

Only one `PushEvent` construction site exists (`router.py:143`), so no other parse path needs the same normalization.

### Positive Notes
- Chooses the correct seam: normalizing the GitHub transport sentinel once at the ingestion boundary keeps the all-zero convention out of the entire domain, and reuses the domain's existing "no prior state" sentinel rather than inventing a new one.
- Correctly instructs *not* to touch `src/versioning/versioner.py`, keeping it specified purely over resolved SHAs — matches the spec guard.
- First-ever staging push with no tags falls through `_next_staging` to `Version(0, 1, 0, prerelease=True)` = `v0.1.0-rc`, exactly the stated goal — provided staging carries work not on the default branch (the only case where a version is meaningful).

### Minor note (non-blocking)
- Task 1 wording — "In `_parse_push_event`, before constructing `PushEvent`, define a module-level constant" — reads as if the constant is defined inside the function; the intent (declare `_CREATION_BEFORE_SHA = "0" * 40` at module scope, apply the mapping inside the function) is unambiguous from the example and the "module-level" phrasing, so the implementer will not be misled. Left as an implementation detail.

## Deferred observations
- Affects: Phase 19 (Boundary representation mismatches) — GitHub sends the same all-zero sentinel as `after` on branch *deletion*, the symmetric case to creation's `before`. This plan intentionally scopes to `before` only (and the spec guards `after` as untouched), so a staging/release-branch deletion push still carries an all-zero `after` downstream. It is out of this task's file boundary and not part of spec 53; flagging only so the phase-19 boundary-mismatch work considers the deletion side explicitly.

PLAN_REVIEW_PASS
