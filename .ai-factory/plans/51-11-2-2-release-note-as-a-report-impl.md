# Plan: 11.2.2 — Release note as a report (impl)

## Context
Express the release note through the existing report engine — a `release_report` factory returning `Report([SummarySection], SinceDeployWindow(role))` — so a release is just a report over the since-deploy window, with no standalone `ReleaseNote` builder and no direct localizer/resolver path.

## Settings
- Testing: no
- Logging: none
- Docs: no

## Tasks

### Phase 1: Release-report factory

- [x] **Task 1: Add `release_report` factory in `src/changelog/release.py`**
  Files: `src/changelog/release.py` (new)
  Create a module-level factory that builds the release note as a `Report`, mirroring the wiring style of `report_for_schedule` (`src/changelog/report.py:100`).

  Signature (governing spec `.ai-factory/specs/20-release-note.md`, echoed in ROADMAP line 110):
  ```python
  def release_report(
      repo: str,
      org_id: int,
      branch: str,
      *,
      mirror: RepoMirror | None = None,
      collector: GitCommitCollector | None = None,
      resolver: LinkedChangeResolver | None = None,
      reasoner: Reasoner | None = None,
  ) -> Report:
  ```
  Body:
  - `role = role_for_branch(branch)` — imported from `src.routing.resolver` (public, `resolver.py:8`). Never re-derive `master`/`main`/`staging` inline here (Guard: branch role compared in one place — 9.1).
  - `window = SinceDeployWindow(mirror, collector, role)` — note `SinceDeployWindow.__init__(mirror, collector, environment)` (`src/changelog/windows/since_deploy.py:19`); `role` (a `BranchRole`) is `environment`.
  - `section = SummarySection(mirror, resolver, reasoner)` — the summary section **only** (a release is what shipped, not what remains); `SummarySection.__init__(mirror, resolver, reasoner)` (`src/changelog/sections/summary.py:17`), `resolver` is a `LinkedChangeResolver`.
  - `return Report(window, [section])`.

  **CRITICAL constructor order — ground truth over spec shorthand:** `Report.__init__(self, window, sections)` takes **window first, then the section list** (`src/changelog/report.py:73`). The spec's `Report([SummarySection], SinceDeployWindow(role))` is conceptual shorthand, not argument order; call `Report(window, [section])`.

  **Keyword-only collaborators default to `None`** exactly as `report_for_schedule` does: this keeps the spec's illustrative verification call `release_report(repo, org_id, "staging")` type-valid, and the window/section fail lazily at `resolve`/`render` if left unwired (the same lazy pattern `TimeWindow` uses). The composition-root caller (11.3) passes the real `mirror`/`collector`/`resolver`/`reasoner`.

  **`repo`/`org_id` are accepted but unused at construction** — they flow to `Localizer.report_notes(report, repo, org_id, langs)` / `Report.build(repo, org_id, lang)` at render time, not into the `Report` object. Document this in the docstring (call-site symmetry with `report_notes`; the window/section resolve `repo` lazily at build time) so their presence is not read as a defect.

  Imports: `Report` from `src.changelog.report`; `SinceDeployWindow` from `src.changelog.windows.since_deploy`; `SummarySection` from `src.changelog.sections.summary`; `role_for_branch` from `src.routing.resolver`; type-only imports `RepoMirror` (`src.github.mirror`), `GitCommitCollector` (`src.commits.collector`), `LinkedChangeResolver` (`src.episodic.linked_change`), `Reasoner` (`src.reasoning.reasoner`).

  Guards satisfied by this construction (no extra code): feature-level over the deploy accumulation (range is `SinceDeployWindow`, not a single push); no language default baked in (this factory never names a language — the caller resolves the union and passes `langs` to `report_notes`); cross-project "unblocks" comes from the reasoner's reach inside `SummarySection` (no separate neighbor finder); no deploy tag → `SinceDeployWindow` spans from repo start (`EMPTY_TREE_SHA`, already handled in `since_deploy.py`).

### Phase 2: Confirm retirement

- [x] **Task 2: Verify no standalone release mechanism exists** (depends on Task 1)
  Confirmed: no-op. No `ReleaseNote`, no release-specific `Localizer.notes`/`LinkedChange.resolve` call, no parallel builder anywhere in `src/`. The only other "release" hits are unrelated prose in the existing summarization slice (`src/summarization/service.py` docstring, `src/summarization/prompt.py` prompt text) — the release path routes solely through `release_report` (Task 1) → `Report` → `Localizer.report_notes`.
  Files: (read-only check — no edit expected)
  The spec directs "Retire `ReleaseNote.build`" and any direct `LinkedChange.resolve`/`Localizer.notes` for a release. Ground truth: no `ReleaseNote`, `release_report`, or release-specific `Localizer.notes`/`LinkedChange.resolve` call exists in `src/` today (only the new `release.py` from Task 1). Confirm the codebase still routes a release solely through `release_report` → `Report` → `Localizer.report_notes`, i.e. no parallel builder was added. If a search surfaces any pre-existing standalone release builder, remove it; otherwise this is a no-op confirmation (record it, do not fabricate a deletion). Do **not** add the 11.3 caller here — wiring the composition root is out of scope for this task.
