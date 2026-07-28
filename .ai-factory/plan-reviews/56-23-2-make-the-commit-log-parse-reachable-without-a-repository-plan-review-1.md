## Plan Review Summary

**Files Reviewed:** 1 plan (`56-23-2-…`) against `src/commits/collector.py`, `src/commits/models.py`, spec `82-collector-log-parse-seam.md`, ROADMAP line 23.2, and all callers of `collect`
**Risk Level:** 🟢 Low

### Context Gates

- **Roadmap** — PASS. The plan heading `23.2 — Make the commit-log parse reachable without a repository` matches ROADMAP line 125 verbatim. The line names `Spec: .ai-factory/specs/82-collector-log-parse-seam.md`.
- **Governing spec (82)** — PASS. Every plan guard maps to a spec guard: additive `parse_log` taking raw text + repo/branch labels (spec §Change), `collect` keeps its signature and delegates, no parsing rule altered "including current defects" (spec §Guards), the new entry point is parse-over-text only — no path, no shell, no filesystem (spec §Guards last bullet), and the 18.2.1/18.2.2 range-failure contract is explicitly left untouched.
- **Architecture** — PASS. Purely additive within the `commits/` feature module; no cross-feature dependency, no composition-root wiring, no new abstraction/interface introduced (`parse_log` is a public method, not a named contract, so the interface-marker convention does not apply).
- **Rules** — PASS. `.ai-factory/RULES.md` is intentionally empty; nothing to check.

### Correctness of the plan against ground truth

- **File path and target method exist.** `src/commits/collector.py` defines `GitCommitCollector` with `_collect_commits` (lines 308–334) holding exactly the record-splitting loop the plan moves: `for record in result.stdout.split(_RECORD_SEP)`, the `if not record.strip()` skip, `self._parse_record(record)`, collect into `tuple(commits)`. The move to `parse_log` operating on `log_text` instead of `result.stdout` is faithful.
- **`_parse_record` / `_parse_tail` untouched.** Confirmed both live in the same file (lines 336–364) and are called by the loop unchanged; leaving them as-is preserves current framing/field/stat/subject-body behaviour exactly, as the guard requires.
- **`core.quotepath=false` preserved.** Task 1 explicitly keeps the `-c core.quotepath=false` arg that 23.1 just landed (line 124, `[x]`); the git invocation at lines 309–326 is retained wholesale by the renamed `_run_log`. The stated dependency ordering (23.1 before 23.2, same invocation) is honoured — no regression of the sibling flag.
- **`collect` delegation is behaviour-preserving.** Current `collect` (lines 32–35) returns `CommitContext(repo=repo_path, branch=branch, commits=…)`. The rewired form `parse_log(log_text, repo=repo_path, branch=branch)` produces the identical context: same `repo` (`repo_path`), same `branch` (via unchanged `_current_branch`), same commit tuple. Signature and return type unchanged.
- **No other caller of the renamed helper.** `_collect_commits` is referenced only at line 34 (inside `collect`) and its definition; the `_collect_commits` → `_run_log` rename is safe. No name collision — no existing `_run_log`.
- **Public callers of `collect` unaffected.** All four call sites — `src/episodic/backfill.py:140`, `src/episodic/linked_change.py:60`, `scripts/eval.py:79`, `scripts/summarize_range.py:41` — use only the unchanged `collect(repo, range)` surface. Spec verification bullet ("every existing caller unchanged") holds.

### Critical Issues

None.

### Positive Notes

- The plan pins the exact seam boundary the spec asks for: `parse_log` is constrained to a pure text parse (no path, no shell, no FS), which is the property that makes the record-separator-in-subject / brace-rename / large-stat cases testable by value rather than by building a repo or patching `subprocess`.
- The rename `_collect_commits` → `_run_log` (returning `str`) correctly severs shell-out from parse, so each side has a single responsibility and the parse becomes reachable — matching the spec's intent precisely.
- Testing:no is the right call: this task only opens the seam; the coverage pass (the separate collector parse test plan) consumes `parse_log` later. No premature test coupling is introduced.

PLAN_REVIEW_PASS
