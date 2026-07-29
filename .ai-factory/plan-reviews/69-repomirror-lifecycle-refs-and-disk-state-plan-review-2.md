## Code Review Summary

**Artifact reviewed:** `.ai-factory/plans/69-repomirror-lifecycle-refs-and-disk-state.md` (test plan, round 2)
**Governing spec:** `.ai-factory/specs/78-repo-mirror-surface-test-plan.md` (ROADMAP_TESTS.md line 19 — "RepoMirror — lifecycle, refs and disk state")
**Target under test:** `src/github/mirror.py`
**Files Reviewed:** 1 plan + 5 grounding files (mirror source, conftest, existing isolation test, governing spec, ROADMAP_TESTS entry)
**Risk Level:** 🟢 Low

Round 1 raised two issues; both are resolved in this revision, and I re-verified the ground-truth facts they turn on. The plan is a faithful, correctly-scoped restatement of spec 78's lifecycle group (cases 1–31, 37–38), excluding the credential group (32–36) and the concurrency/async surface (20.2.x) exactly as the contract line requires.

### Context Gates
- **Architecture** (`.ai-factory/ARCHITECTURE.md`): OK — test-only plan, adds one file under `tests/github/`, touches no `src/` and no module boundary.
- **Rules** (`.ai-factory/RULES.md`): OK — file is intentionally empty (no project counter-defaults); nothing to violate.
- **Roadmap** (`.ai-factory/ROADMAP_TESTS.md` line 19): OK — plan scope ("everything except the credential group and concurrency/async") matches the contract line and its guards (deferred reclamation, disk-vs-git-list separation) verbatim.
- **skill-context** (`.ai-factory/skill-context/aif-review/SKILL.md`): absent — no project-specific overrides.

### Round-1 issues — both resolved

**1. Task 5 HEAD-tracking case (was Critical Issue 1) — FIXED and verified.**
The case is now `should track upstream's HEAD, refreshed on each ensure, when upstream's default branch moves` (plan line 72), and its **Verified git behavior** note correctly states the *tracking* contract, drops the false "known limitation" framing, and pins the escalation path if the team ever wants non-drift. I independently reproduced the exact `ensure` command sequence on git 2.50.1: after `git clone --mirror` bare HEAD = `feature`; after `git -C up symbolic-ref HEAD refs/heads/trunk` + `git fetch --prune origin` bare HEAD = `trunk` (`remote.origin.mirror=true`). So `default_branch` tracks upstream's HEAD across `ensure`, and the corrected case is green against correct code.

**2. Task 5 never-ensured case (was Minor Issue 2) — FIXED and verified.**
The case `should raise rather than return an empty string when the repo was never ensured` (plan line 74) now explicitly states **`FileNotFoundError`**, not `CalledProcessError`, and the Fixtures & Conventions block (line 25) carves this out as the one case exempt from the "assert `CalledProcessError` type/returncode only" rule. Confirmed against the real call: `subprocess.run([...], cwd=<missing dir>, check=True)` raises `FileNotFoundError` at spawn (`chdir` failure), before git runs.

### Critical Issues
None.

### Positive Notes
- **Complete, correctly-scoped coverage.** All of spec 78's lifecycle cases map cleanly onto the 9 tasks; credential (32–36) and concurrency/async (20.2.x) excluded per the ROADMAP_TESTS line and spec scope-guard.
- **Deferred-reclamation contract pinned correctly** — the plan repeatedly forbids `not path.exists()` right after a `with mirror.tree(...)` block and asserts absence only after the next `ensure`, matching the source rationale (mirror.py:133–163). Task 4's raise-inside-`with` case (line 63) correctly checks that the exception path registers for reclamation and does not leak disk.
- **Disk vs. `git worktree list --porcelain` treated as two independent observables** — matches the divergence `worktree prune` exists for; sweep and reclamation cases assert both.
- **Source-grounded git facts re-confirmed:** clone-vs-fetch keyed on bare-path existence; `--prune` drops deleted refs; force-push adoption via the mirror refspec; the `mkdtemp`-before-failing-`worktree add` leak in Task 4's missing-ref case (mirror.py:153 runs before the try/finally, so the scratch dir is never registered) is real and correctly pinned as decision-on-record; `resolve_canonical_ref`'s `override is not None` making `""` a real override (mirror.py:216); reclamation keyed by bare path, not global (mirror.py:167).
- **Restart modeled as a fresh `RepoMirror` over the same `mirror_root`** — the only faithful stand-in for the in-memory, per-instance `_finished_worktrees` list; used correctly for the sweep cases.
- **Non-recursive `glob("*.git")` and flat-layout gap** called out to document-not-fix, consistent with the slash-free `clone_source` naming — good restraint.

## Deferred observations
- Affects: `.ai-factory/specs/78-repo-mirror-surface-test-plan.md` (case 18, line 51) — the governing spec still frames the moved-upstream-HEAD case as a "known limitation … `git fetch --prune` does not update a mirror's local HEAD (that needs `git remote set-head`)." That is false for the `--mirror` clone `ensure` actually creates: with `remote.origin.mirror=true`, `fetch --prune origin` *does* follow upstream's HEAD (reproduced on git 2.50.1). The plan already overrides this correctly and flags the spec for correction; the fix itself is a governing-spec edit outside this test-plan's file boundary (`tests/github/test_mirror_lifecycle.py`), so it is left for the spec owner rather than blocking the plan. [dismissed]

PLAN_REVIEW_PASS
