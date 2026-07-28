# Code Review: 10.3 — Report localization

**Plan:** `.ai-factory/plans/48-10-3-report-localization.md`
**Files reviewed (code):** `src/reasoning/localizer.py`, `scripts/report.py`, `tests/reasoning/conftest.py`, `tests/reasoning/test_localizer.py`
**Risk level:** 🟢 Low

## Scope

The diff routes the composed `Report` through the existing `Localizer` seam per required language (Task 1–4 of the plan). Planning artifacts (`.ai-factory/plan-reviews/*`, `.ai-factory/plans/48-*`) are also staged but are not code and were not reviewed for correctness.

## Verification performed

- Read all four changed source files in full, plus the surrounding `Localizer`/`Report`/`ReportSection` context and the composition-root wiring in `scripts/report.py`.
- `uv run pytest tests/reasoning/test_localizer.py` → **15 passed**.
- Full suite `uv run pytest` → **155 passed**.
- `scripts/report.py` parses; imports (`PivotLocalizer`, `LLMTranslator`) resolve.
- Confirmed no `Localizer` subclass other than `PivotLocalizer`/`NativeLocalizer` exists, so adding `report_notes` as an `@abstractmethod` breaks no other implementer.

## Correctness assessment

- **Dependency direction held.** `report_notes` types its `report` argument via a structural `ReportProtocol(typing.Protocol)` declared inside `reasoning`; no `changelog` import is introduced, preserving the `changelog → reasoning` one-way rule. The composition root (`scripts/report.py`) passes the concrete `Report`, which structurally satisfies the Protocol.
- **Pivot dispatch mirrors `notes` exactly.** `report.build` is called once for `self._pivot`; the pivot's own text is returned untranslated when requested; every other lang goes through `translate(pivot_text, target_lang=lang, source_lang=self._pivot)`; empty `langs` → `{}` with zero build/translate. Verified by call-count tests.
- **`None`-report edge handled and tested.** When the pivot build returns `None`, every lang maps to `None` with zero `translate` calls (no `None` text is ever passed into `translate`); `NativeLocalizer` maps each lang to `None` independently. Both branches are exercised by dedicated tests — closing the silent-failure surface the plan review flagged.
- **`ReportProtocol.build` signature matches `Report.build`** (`repo, org_id, lang="ru") -> str | None`) exactly.
- **Composition root + consumption correct.** `PivotLocalizer(reasoner, LLMTranslator(llm), pivot=settings.pivot_lang)` reuses the already-built `llm`/`reasoner`. The per-repo loop calls `report_notes(report, repo, org_id, {plan.language})` and reads `notes.get(plan.language)`, correctly handling the widened `str | None` value; the existing `skipped_empty` / `skipped_no_channel` control flow and the per-repo exception guard are untouched. No parallel localization path introduced.
- **Return type honestly widened** to `dict[str, str | None]` — grounded in the fact that `Report.build` really can return `None` (unlike `narrate`).

## Findings

None. The change is implementable, architecturally sound, and fully tested; no correctness, type, or runtime-breakage issues found. No migrations or schema changes are involved.

REVIEW_PASS
