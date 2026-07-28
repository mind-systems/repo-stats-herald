# Plan Review: GitCommitCollector — the commit-log parse (round 3)

## Code Review Summary

**Artifact reviewed:** `.ai-factory/plans/68-gitcommitcollector-the-commit-log-parse.md` (test plan)
**Chain walked:** plan → `ROADMAP_TESTS.md:18` line ("GitCommitCollector — the commit-log parse") → governing spec `.ai-factory/specs/77-commit-collector-parse-test-plan.md` → `src/commits/collector.py`, `src/commits/models.py`, `tests/commits/{conftest.py,test_collector.py}` → commit `d47f195` (task 23.6, framing fix) → prior reviews `…-plan-review-1.md`, `…-plan-review-2.md`.
**Files Reviewed:** 7
**Risk Level:** 🟢 Low

The plan is well-grounded and tracks the *current* code, not the pre-framing-fix shapes the spec body still narrates. It correctly follows the spec's own "Seam in place" section: the public `parse_log` seam, `_run_log` carrying `-c core.quotepath=false`, case 17 as a positive assertion, case 4 (RS-in-subject) held out of scope, and the parse/collect split.

**All issues from prior rounds are resolved:**
- Round-1 #1 (`_collect_commits` stale reference) — fixed; Task 4 header now reads "`collect` / `_run_log` / `parse_log` end-to-end" (plan line 64), matching `collect`'s delegation at `collector.py:35-38`; `_collect_commits` no longer exists.
- Round-1 #2 (self-contradictory `_merge`/`_checkout_new_branch` guidance) — fixed; line 24 states the collect group needs only `_git`, and case 14 is captured once offline as a text constant with no merge helper at runtime.
- Round-1 #3 ("leading record separator" naming) — fixed; the framing case is now `should not emit a phantom empty Commit for the leading NUL marker …` (line 68).
- Round-2 #1 (`_git` false-premise / "lift into conftest") — fixed; line 24 now correctly states `conftest.py:11` **already** provides `_git(*args, cwd, env=None)`, offers "use the existing conftest `_git` or redefine one locally", and explicitly forbids overwriting/shadowing the conftest definition whose `env` parameter is load-bearing for `commit_at(when=…)`.

Independently re-verified against ground truth:
- `parse_log(log_text, repo, branch)` is public and pure — no shelling out (`collector.py:311-338`); split-on-NUL then group-by-5 yields exactly the empty leading field the framing case targets (`collector.py:327-338`).
- `_run_log` carries `-c core.quotepath=false` (`collector.py:342-343`), so case 17 (non-ASCII path) is correctly a straight positive assertion.
- `_NUMSTAT_RE` accepts `-` counts for binaries and `_SHORTSTAT_RE` tolerates `files?`; `_parse_tail` strips the leading space (`collector.py:19-20,379-389`).
- `_current_branch` runs `check=True` and returns the literal `"HEAD"` when detached (`collector.py:302-309`); `_run_log` runs `check=True` (`collector.py:358`), backing Task 7's `CalledProcessError` case.
- `EMPTY_TREE_SHA` is exported (`collector.py:26`), backing Task 7's sentinel case.
- `commit_at` → `_commit` commits `--allow-empty` with nothing staged (`conftest.py:15-25`, `commit_at` at 38-48), grounding the "stage a real file with `add -A` first" caveat.
- `conftest.py:11` defines the superset `_git(*args, cwd, env=None)`; `test_collector.py:12` holds a separate `env`-less local `_git` — the plan describes this relationship accurately.
- Scope guards hold: the RS regression tests do live at `test_collector.py:167-195` (subject and body variants); `d47f195` is a real commit titled "23.6 — Frame the commit log on a boundary a message cannot forge" touching `src/commits/collector.py` and `tests/commits/test_collector.py`; `new_commits` failure signal is left untouched.

Every test case maps to a real, reachable branch of `parse_log` / `collect` / `_parse_record` / `_parse_tail`. The NUL-field isolation reasoning behind Task 2's two injection guards is sound — a shortstat/numstat-shaped line placed in the body field sits before the fourth NUL and never reaches `_parse_tail`, which only scans the trailing field.

### Context Gates
- **Architecture** (`.ai-factory/ARCHITECTURE.md`): PASS. Test-only plan; no boundary or DI impact.
- **Rules** (`.ai-factory/RULES.md`): PASS. No test/fixture convention conflict.
- **Roadmap** (`.ai-factory/ROADMAP_TESTS.md:18`): PASS. The plan refines the correct contract line and its `Spec: 77`. (The plan filename prefix "68" collides with an unrelated main-roadmap spec file `68-foreign-product-name-sweep.md` — a plans-dir naming collision, not a plan defect, as both prior reviews noted.)
- **Skill-context** (`.ai-factory/skill-context/aif-review/SKILL.md`): absent — no project overrides.

### Critical Issues
None. No missing steps, migrations, security holes, incorrect file paths, wrong API usage, or architectural mistakes. The plan is implementable as written.

### Positive Notes
- Routes injection / rename / merge / large-block cases through the pure `parse_log` seam as string-in / `CommitContext`-out, keeping the honest end-to-end cases on the `git_repo` / `commit_at` fixtures — exactly the split the spec's "Seam in place" section prescribes.
- Faithfully carries the spec's hard-won empirical facts: brace-compressed rename form (`dir/{old => new}/file.md`), space-prefixed shortstat, singular `file`, binary `-` counts, newest-first ordering, and the empty-tree asymmetry with `active_branches`.
- Scope guards are precise and attributed to their owning open tasks (18.2.1 / 18.2.2 for the `new_commits` failure signal, 23.6 for the already-landed RS regression), and explicitly protect the landed regression tests from duplication.
- The `--numstat`-vs-`--stat` rationale is preserved as a real regression guard (untruncated long-path case), not decoration.

PLAN_REVIEW_PASS
