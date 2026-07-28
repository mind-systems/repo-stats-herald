# Plan Review: GitCommitCollector — the commit-log parse (round 2)

## Code Review Summary

**Artifact reviewed:** `.ai-factory/plans/68-gitcommitcollector-the-commit-log-parse.md` (test plan)
**Chain walked:** plan → `ROADMAP_TESTS.md` line ("GitCommitCollector — the commit-log parse") → governing spec `.ai-factory/specs/77-commit-collector-parse-test-plan.md` → `src/commits/collector.py`, `src/commits/models.py`, `tests/commits/{conftest.py,test_collector.py}` → prior review `…-plan-review-1.md`.
**Files Reviewed:** 6
**Risk Level:** 🟢 Low

The plan is well-grounded and tracks the *current* code, not the pre-framing-fix shapes the spec body still narrates. All three non-blocking issues raised in review-1 are resolved in this revision:

1. **`_collect_commits` stale reference — fixed.** Task 4's header now reads "`collect` / `_run_log` / `parse_log` end-to-end" (plan line 64), matching ground truth: `collect` delegates to `_run_log` + `parse_log` (`collector.py:35-38`) and `_collect_commits` no longer exists.
2. **Self-contradictory `_merge`/`_checkout_new_branch` guidance — fixed.** The Fixtures section (line 24) now states the collect group needs only `_git`, and that the single merge scenario (case 14, Task 3) is captured once offline as a text constant with no merge helper at runtime.
3. **"leading record separator" naming — fixed.** Task 4's second case is now `should not emit a phantom empty Commit for the leading NUL marker …` (line 68), matching the NUL-framing design (`log_text.split("\x00")`, `collector.py:327`).

Independently verified against the code: `parse_log` is public and pure (`collector.py:311-338`); split-on-NUL then group-by-5 yields exactly the empty leading field the framing case targets; `_run_log` carries `-c core.quotepath=false` (`collector.py:345`), so case 17 is correctly a positive assertion; `_NUMSTAT_RE` accepts `-` counts and `_SHORTSTAT_RE` tolerates `files?` with a space-prefixed line stripped by `_parse_tail` (`collector.py:19-20,379-389`); `_current_branch` uses `check=True` and returns the literal `"HEAD"` when detached (`collector.py:302-309`); `EMPTY_TREE_SHA` is exported (`collector.py:26`); `commit_at`→`_commit` commits `--allow-empty` with nothing staged (`conftest.py:15-25`). Every test case maps to a real, reachable branch. Scope guards (`new_commits` failure signal owned by 18.2.x, the RS regression already landed at `test_collector.py:167-195`, no `src/` edits) match ground truth.

### Context Gates
- **Architecture** (`.ai-factory/ARCHITECTURE.md`): PASS. Test-only plan; no boundary or DI impact.
- **Rules** (`.ai-factory/RULES.md`): PASS. No test/fixture convention conflict.
- **Roadmap** (`.ai-factory/ROADMAP_TESTS.md:18`): PASS. The plan refines the correct contract line and its `Spec: 77`. (The plan's filename prefix "68" collides with an unrelated main-roadmap spec file — a plans-dir naming collision, not a plan defect, as review-1 already noted.)
- **Skill-context** (`.ai-factory/skill-context/aif-review/SKILL.md`): absent — no project overrides.

### Critical Issues
None. No missing steps, migrations, security holes, or architectural mistakes. The plan is implementable as written; the collect group has a safe path (see below).

### Non-blocking Issues (fixable within this task)

1. **Wrong assumption: `_git` is treated as living only in `test_collector.py`, but a superset already lives in `conftest.py` — and the "lift into conftest" instruction would break `commit_at`.**
   Plan line 24 says: "*Module-level helper `_git` currently lives in `test_collector.py`. … Reuse it by lifting it into `tests/commits/conftest.py` as a plain module function (or redefine it locally).*" Ground truth: `tests/commits/conftest.py:11` **already** defines `_git(*args, cwd, env=None)` — a superset with an `env` parameter — and `test_collector.py:12` holds a *separate* local `_git(*args, cwd)` without `env`. The conftest `_git`'s `env` parameter is load-bearing: `_commit` (`conftest.py:15-25`) calls `_git(..., env=env)` for `commit_at(when=…)`, exercised by `test_collector.py`'s timestamp tests. Following the "lift [test_collector's `_git`] into conftest.py" branch literally would add a second, `env`-less `_git` in `conftest.py` that shadows the existing one and makes every `commit_at(when=…)` call raise `TypeError`. The plan's parenthetical "(or redefine it locally)" is the safe path and matches how `test_collector.py` already does it, so this is non-blocking — but the primary instruction rests on a false premise. Recommend: state that `conftest.py` already provides a reusable `_git(*args, cwd, env=None)`, drop the "lift it into conftest" option (it is already there and must keep its `env` param), and have each new module redefine `_git` locally or use the conftest one — never overwrite the conftest definition.

### Positive Notes
- Correctly routes injection / rename / merge / large-block cases through the pure `parse_log` seam as string-in / `CommitContext`-out, and keeps the honest end-to-end cases on the `git_repo`/`commit_at` fixtures — exactly the split the spec's "Seam in place" section prescribes.
- Faithfully carries the spec's hard-won empirical facts: brace-compressed rename form (`dir/{old => new}/file.md`), space-prefixed shortstat, singular `file`, binary `-` counts, newest-first ordering, and the empty-tree asymmetry with `active_branches`.
- The `commit_at`-makes-empty-commits caveat is reproduced accurately and drives the "stage a real file with `add -A` first" instruction in Task 5.
- Scope guards are precise and attributed to their owning open tasks; the already-landed RS regression tests are explicitly protected from duplication.
