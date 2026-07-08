# 10.3 — Report localization

**Phase:** 10 — Reporting engine (composable reports). Depends on 10.1.2 (report + sections), 8.2 (`Localizer`). After 10.2.

## Current state

`Report.build` produces the report in one language, calling the reasoner directly. Release notes (11.2) already route through the `Localizer` (8.2); the report is the one narration path still bypassing the localization seam.

## Change

Route the composed report through the `Localizer`, per required language, reusing 8.2's pivot/native strategy.

- Extend `Localizer` (8.2) with the report shape: `report_notes(report: Report, repo: str, org_id: int, langs: set[str]) -> dict[str, str]` — `PivotLocalizer` builds the report in the pivot language **once** and `translate`s the assembled text to the rest; `NativeLocalizer` builds the report **per language** (its sections narrated per language). The section narration threads `lang` end-to-end.
- 10.2's entrypoint calls `Localizer.report_notes(...)` for the delivering channel's required language(s) instead of building the report directly.

## Files & types

- edit `src/reasoning/localizer.py` (`Localizer.report_notes`, both implementations)
- edit `src/changelog/report.py` / sections to thread `lang`
- edit `scripts/report.py` (build via the localizer)

## Guards

- Reuses the existing `Localizer` strategy — no parallel localization path for reports.
- Default single-language (`"ru"`) output is unchanged; only the code path changes.
- **Mandatory call-count test (mirroring 8.2.1, over a mocked report/section narration + mocked `translate`):** `PivotLocalizer.report_notes(..., {ru,en})` (pivot en) → the report narrated **once** (in en) + `len(langs)-1` `translate` calls, the pivot untranslated; `NativeLocalizer.report_notes(..., {ru,en})` → the report narrated `len(langs)` times, one per language. A pivot that quietly narrates per language defeats the pivot with no crash.

## Verification

- A report delivered to a non-`"ru"` channel is produced in that language via the localizer (canonical-pivot default), not hardcoded `"ru"`.
- Swapping the composition root's `Localizer` implementation changes the report's strategy too, with no change to `Report`.
