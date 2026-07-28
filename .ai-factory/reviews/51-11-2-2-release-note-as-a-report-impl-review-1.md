# Code Review: 11.2.2 — Release note as a report (impl)

**Files reviewed (code):** `src/changelog/release.py` (new, 43 lines). The other staged files are planning artifacts (plan, plan JSON, plan-review), not code.
**Risk level:** 🟢 Low
**Result:** No bugs, security issues, or correctness problems found.

## What the change does

Adds a single module-level factory `release_report(repo, org_id, branch, *, mirror, collector, resolver, reasoner) -> Report` that expresses the release note through the existing report engine: `Report(SinceDeployWindow(role), [SummarySection(...)])`, with `role = role_for_branch(branch)`. No standalone `ReleaseNote` builder, no direct `LinkedChange.resolve`/`Localizer.notes` path — the release is just a report over the since-deploy window, as the spec requires.

## Verification performed

- **Syntax + runtime import/call (via `uv run`):** `release_report('repo', 1, 'staging')` returns a `Report` with 1 section and a `SinceDeployWindow` whose `environment` is `BranchRole.STAGING`; `release_report('main', 2, 'main')` yields `BranchRole.RELEASE`. Construction with the default `None` collaborators succeeds (lazy wiring), matching the spec's illustrative `release_report(repo, org_id, "staging")` call.
- **Full changelog test suite:** `pytest tests/changelog/` → 36 passed. No regression from the new module.
- **Constructor orders confirmed against ground truth:** `Report.__init__(self, window, sections)` window-first (`report.py:73`) — call is `Report(window, [section])` ✓. `SinceDeployWindow.__init__(mirror, collector, environment)` (`since_deploy.py:19`) ✓. `SummarySection.__init__(mirror, resolver, reasoner)` (`summary.py:17`) ✓.
- **Guards satisfied:** branch role compared in exactly one place (`role_for_branch`, no inline `master`/`staging` compare); summary section only (release = what shipped); no language baked in (factory names no language; caller resolves the union for `report_notes`); cross-project "unblocks" inherited from `SummarySection`'s reasoner reach; no deploy tag → repo start already handled inside `SinceDeployWindow`.
- **Retirement guard:** no `ReleaseNote`/parallel release builder exists anywhere in `src/` — confirmed, nothing to remove.

## Notes on the implementation (all acceptable, no action required)

- **`TYPE_CHECKING`-guarded collaborator imports.** The implementer put `RepoMirror`/`GitCommitCollector`/`LinkedChangeResolver`/`Reasoner` under `if TYPE_CHECKING` with string annotations, rather than importing them at runtime as the plan's "Imports" line listed. This is *better* than the plan asked: those symbols are only used as annotations, so deferring them keeps the module import-light and sidesteps any import-cycle risk. `role_for_branch`, `Report`, `SinceDeployWindow`, `SummarySection` are correctly runtime imports (they are called/instantiated). Verified to import and run cleanly.
- **`repo`/`org_id` accepted but unused at construction.** Correct and documented in the docstring — they flow to `Localizer.report_notes(report, repo, org_id, langs)` / `Report.build(repo, org_id, lang)` at render time, not into the `Report`. Faithful to the spec's mandated signature and its verification call shape.

## Deferred observation (non-blocking, not a defect in this task)

- **No guard against a non-release/staging `branch`.** If `release_report` is ever called with a DEV branch (e.g. `feature/x`), `role_for_branch` returns `BranchRole.DEV`, construction still succeeds, and the failure surfaces later as `ValueError("unsupported environment: BranchRole.DEV")` from `SinceDeployWindow.resolve` (`since_deploy.py:25-26`) at render time. This is a *fail-loud* outcome with a clear message, not a silent-wrong-output bug, and the intended caller (11.3) only invokes this on release/staging pushes where `branch` is the real push ref — so DEV cannot reach here in the designed flow. Noted only so a future reader knows the factory itself does not reject DEV; adding an early guard is out of scope for this construction-only task and would be redundant with the window's own check.

REVIEW_PASS
