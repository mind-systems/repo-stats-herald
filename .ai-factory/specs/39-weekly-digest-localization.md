# 10.3 — Report localization

**Phase:** 10 — Reporting engine (composable reports). Depends on 10.1.2 (report + sections), 8.2 (`Localizer`). After 10.2.

## Current state

`Report.build` produces the report in one language, calling the reasoner directly. Release notes (11.2) already route through the `Localizer` (8.2); the report is the one narration path still bypassing the localization seam.

## Change

Route the composed report through the `Localizer`, per required language, reusing 8.2's pivot/native strategy.

- Extend `Localizer` (8.2) with the report shape: `report_notes(report: Report, repo: str, org_id: int, langs: set[str]) -> dict[str, str]`, with the **same dispatch as `notes` (8.2.1)** — `PivotLocalizer` builds the report **once** in the pivot (`report.build(repo, org_id, pivot)`) and `translate`s the assembled text to every requested language except the pivot (`source_lang=pivot`), returning the pivot's own text only when the pivot is itself requested; `NativeLocalizer` builds the report **per requested language** (`report.build(repo, org_id, lang)`, sections narrated in that `lang`); empty `langs` → empty dict with no builds/translates; result keys == `langs` exactly. The section narration threads `lang` end-to-end via `render`/`build` (10.1.1).
- 10.2's entrypoint calls `Localizer.report_notes(...)` for the delivering channel's required language(s) instead of building the report directly.

## Files & types

- edit `src/reasoning/localizer.py` (`Localizer.report_notes`, both implementations)
- edit `src/changelog/report.py` / sections to thread `lang`
- edit `scripts/report.py` (build via the localizer)

## Guards

- Reuses the existing `Localizer` strategy — no parallel localization path for reports.
- Default single-language (`"ru"`) output is unchanged; only the code path changes.
- **Mandatory call-count test (mirroring 8.2.1, over a mocked report/section narration + mocked `translate`):** `PivotLocalizer.report_notes(..., {ru,en})` (pivot en) → the report built **once** (in en) + one `translate` per requested language other than the pivot (here `ru`, `source_lang=en`), the pivot untranslated and returned only because it's requested; `NativeLocalizer.report_notes(..., {ru,en})` → the report built `len(langs)` times, one per language; empty `langs` → empty dict, zero builds. A pivot that quietly builds per language defeats the pivot with no crash.

## Verification

- A report delivered to a non-`"ru"` channel is produced in that language via the localizer (canonical-pivot default), not hardcoded `"ru"`.
- Swapping the composition root's `Localizer` implementation changes the report's strategy too, with no change to `Report`.
