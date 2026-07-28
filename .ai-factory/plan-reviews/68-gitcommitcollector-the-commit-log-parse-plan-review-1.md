# Plan Review: GitCommitCollector — the commit-log parse

## Code Review Summary

**Artifact reviewed:** `.ai-factory/plans/68-gitcommitcollector-the-commit-log-parse.md` (test plan)
**Chain walked:** plan → `ROADMAP_TESTS.md` line ("GitCommitCollector — the commit-log parse") → governing spec `.ai-factory/specs/77-commit-collector-parse-test-plan.md` → `src/commits/collector.py`, `src/commits/models.py`, `tests/commits/{conftest.py,test_collector.py}` → commit `d47f195` (task 23.6, framing fix).
**Risk Level:** 🟢 Low

The plan is well-grounded. It correctly tracks the *current* code (NUL-based framing via `_PRETTY_FORMAT`, the public `parse_log` seam, `_run_log` carrying `-c core.quotepath=false`) rather than the pre-framing-fix shapes that the spec's body still describes. The spec's own "Seam in place" section (lines 88–124) already flags those updates, and the plan applies them faithfully: case 17 is a positive assertion, case 4 (RS-in-subject) is held out of scope, and the parse/collect split is honored. The scope guards (`new_commits` failure signal owned by 18.2.x, the record-separator regression already landed in `test_collector.py`, no `src/` edits) all match ground truth — the two RS regression tests do live at `test_collector.py:167-195`, and `d47f195` is a real commit.

The critical instantiation caveats are accurate against the code: `commit_at` (conftest) does commit `--allow-empty` with nothing staged; `_run_log` does set `core.quotepath=false` (`collector.py:345`); `_NUMSTAT_RE` does accept `-` counts for binaries; `_SHORTSTAT_RE` does tolerate `files?` and `_parse_tail` strips the leading space; `_current_branch` uses `check=True` and returns the literal `"HEAD"` when detached; `EMPTY_TREE_SHA` is exported. The `parse_log` split-on-NUL / group-by-5 mechanism produces exactly the "empty leading element" the plan's framing case targets.

### Context Gates
- **Architecture** (`ARCHITECTURE.md`): PASS. Test-only plan, no boundary/DI impact.
- **Rules** (`RULES.md`): PASS. No test/fixture convention conflicts.
- **Roadmap** (`ROADMAP_TESTS.md`): PASS. The plan links to and refines the correct contract line and its `Spec:` (77). Note the plan's title number "68" is the spec-file number of an *unrelated* main-roadmap task (22.1, `68-foreign-product-name-sweep.md`); the governing spec for this work is `specs/77-...`. This is just a filename collision in the plans dir, not a plan defect.
- **Skill-context** (`.ai-factory/skill-context/aif-review/SKILL.md`): absent — no project overrides.

### Critical Issues
None. No missing steps, migrations, security issues, or architectural mistakes. The plan is implementable as written and each test case maps to a real, reachable branch of `parse_log`/`collect`/`_parse_record`/`_parse_tail`.

### Non-blocking Issues (fixable within this task)

1. **Stale code reference: `_collect_commits` no longer exists.** Task 4's header reads "record framing, ordering, empty range (`_collect_commits` / `parse_log` end-to-end)". That method was removed when the NUL-framing fix (`d47f195`) landed — `collect` now delegates to `_run_log` + `parse_log`, and `grep -rn _collect_commits src/ tests/` returns nothing. The spec body still names `_collect_commits` (lines 8/38), but the spec's own "Seam in place" section supersedes that. An implementer following the Task 4 header would look for a method that isn't there. Replace the reference with `collect` / `_run_log` / `parse_log`.

2. **Self-contradictory fixtures instruction re `_merge` / `_checkout_new_branch`.** The "Fixtures & helpers" section (line 24) says "The collect group needs `_git` ... and `_merge`/`_checkout_new_branch` (case 14 only, and case 14 is in the parse group)." Case 14 (the merge case) is Task 3 in the **parse group**, which is driven entirely by captured text constants — no live git, no merge helper at runtime. So no runtime test in either new module actually calls `_merge`/`_checkout_new_branch`; only `_git` (staging, non-ASCII author, detached HEAD) is needed. As written, the instruction would lead an implementer to lift/redefine merge helpers that no test uses. Recommend narrowing the "reuse/lift" guidance to `_git` only, and stating that the merge block for case 14 is captured once, offline, from real git output.

3. **Naming imprecision: "leading record separator".** Task 4's second case is named `should not emit a phantom empty Commit for the leading record separator ...`. Since the framing fix, the record marker is the NUL byte (`%x00`), not the ASCII record separator (`\x1e`); the empty leading element now comes from `log_text.split("\x00")`, not an RS split. The case's own explanatory text ("the format prefixes every record with the marker") is accurate — only the "record separator" wording is stale. Consider "leading NUL marker" (or just "leading empty field") so the emitted test name doesn't carry a term that describes the superseded design.

### Positive Notes
- Correctly recognizes that `parse_log` is a pure seam and routes the injection/rename/merge/large-block cases through it as string-in / `CommitContext`-out, avoiding fixture-repo fragility.
- Faithfully carries the spec's hard-won empirical facts: brace-compressed rename form (`dir/{old => new}/file.md`), space-prefixed shortstat, singular `file`, binary `-` counts, newest-first ordering, and the empty-tree asymmetry with `active_branches`.
- Scope guards are precise and correctly attributed to their owning open tasks; the already-landed RS regression tests are explicitly protected from duplication.
- The `--numstat`-vs-`--stat` rationale (untruncated long-path case) is preserved as a real regression guard, not decoration.
