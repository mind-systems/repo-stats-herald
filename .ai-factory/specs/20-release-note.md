# 11.2.2 — Release note as a report (impl)

**Phase:** 11 — GitHub releases & versioning. Depends on 11.2.1 (`SinceDeployWindow`), 10.1.2 (`SummarySection`), 10.1.1 (`Report`/`report_notes`), 8.2 (the localizer). Produces the release note through the report engine — no standalone builder.

## Current state

The report engine (Phase 10) composes sections over a window and localizes via `Localizer.report_notes`. A release note is the same thing on the release trigger: a **summary of what shipped since the last deploy**. It must not be a second, parallel mechanism (`docs/spec/narration.md#reports` states the engine expresses the release note too). The standalone `ReleaseNote.build`/`LinkedChange.resolve`/`Localizer.notes` path is retired.

## Change

- A release report is `Report([SummarySection], SinceDeployWindow(environment))` — the summary section only (a release is what shipped, not what remains), windowed since the last deploy. Environment from the branch: default branch → release, `staging` → staging.
- `src/changelog/release.py` — `release_report(repo: str, org_id: int, branch: str) -> Report`: constructs that report. The caller (11.3) renders it per its required languages via `Localizer.report_notes(report, repo, org_id, langs)` (10.3) — one resolution, one set of notes, the pivot/native strategy owned by the localizer.
- **Retire** `ReleaseNote.build`; nothing calls `LinkedChange.resolve`/`Localizer.notes` for a release directly.

## Files & types

- rewrite `src/changelog/release.py` (`release_report` returns a `Report`; the old `ReleaseNote` builder removed)

## Guards

- Feature-level over the deploy accumulation — the range is `SinceDeployWindow`, not a single push (a served push is memory-only; the release note narrates from memory over the accumulation).
- Multi-language is `report_notes`' concern — this task does not call `Reasoner.narrate` or `Localizer.notes` directly, and bakes in no default language set (the caller 11.3 resolves the union).
- Cross-project "unblocks" comes from the reasoner's reach (7.2) inside `SummarySection` — no separate `NeighborFinder`.
- No deploy tag → `SinceDeployWindow` spans from the repo start, without crashing.

## Verification

- `report_notes(release_report(repo, org_id, "staging"), repo, org_id, {"ru","en"})` → a note covering everything since the last deploy tag, in both languages, from one resolution.
- A default-branch release report → the accumulation since the last full release.
- A third language costs no extra resolution (report_notes handles it).
- Notes for different languages describe the same change set.
