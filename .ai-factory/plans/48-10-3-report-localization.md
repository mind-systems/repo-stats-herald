# Plan: 10.3 — Report localization

## Context
Route the composed `Report` through the existing `Localizer` seam (8.2) per required language, reusing 8.2.1's pivot/native dispatch, so a report is produced in the delivering channel's language via the swappable strategy instead of a hardcoded single-language `Report.build`.

## Settings
- Testing: yes
- Logging: minimal
- Docs: no

## Grounding notes (read before implementing)

- **Dispatch to mirror:** `src/reasoning/localizer.py` — `PivotLocalizer.notes` (narrate once in pivot + `translate` each non-pivot lang with `source_lang=pivot`; pivot returned untranslated only when requested; empty `langs` → `{}`) and `NativeLocalizer.notes` (one narration per lang). `report_notes` mirrors this exactly, substituting `report.build(repo, org_id, lang)` for `reasoner.narrate(change, lang)`.
- **Dependency direction is fixed:** the guard on 10.1.2 pins `changelog → reasoning` **one-way**. `localizer.py` (in `reasoning`) must **not** import `Report` from `changelog`. Type the `report` argument via a structural `typing.Protocol` declared in `reasoning`, not a concrete import.
- **`lang` is already threaded** end-to-end: `Report.build(…, lang)` (src/changelog/report.py) passes `lang` to each `ReportSection.render(…, lang)`, and all three sections consume it — `SummarySection`/`PerBranchSection` pass it to `Reasoner.narrate(change, lang)`, `RemainingSection` to `RemainingPromptBuilder.build(tasks, lang)`. No section threading change is expected; Task 3 only verifies this.
- **`Report.build` can return `None`** (all sections `None`). `notes` never faces a `None` narration, so `report_notes` must define this edge explicitly (see Task 1).
- **Wiring precedent:** `scripts/eval.py` (~line 230) already builds `PivotLocalizer(reasoner, LLMTranslator(OllamaClient(...)), pivot=settings.pivot_lang)` — `scripts/report.py` follows the same shape. `settings.pivot_lang` defaults to `"en"` (src/core/config.py).
- **Test precedent:** `tests/reasoning/test_localizer.py` + `tests/reasoning/conftest.py` (`fake_narrating_reasoner`, `fake_translator`, `make_change`). The new call-count test mirrors those, swapping in a fake report.

## Tasks

### Phase 1: Localizer.report_notes

- [x] **Task 1: Add `report_notes` to the `Localizer` seam and both strategies**
  Files: `src/reasoning/localizer.py`
  Add a structural `ReportProtocol(typing.Protocol)` with the single method
  `async def build(self, repo: str, org_id: int, lang: str = "ru") -> str | None: ...`
  (declared in this module so `reasoning` never imports `changelog`).
  Add an abstract method to `Localizer`:
  `async def report_notes(self, report: ReportProtocol, repo: str, org_id: int, langs: set[str]) -> dict[str, str | None]`.
  Implement it in both strategies, mirroring the existing `notes` dispatch exactly:
  - `PivotLocalizer.report_notes`: empty `langs` → `{}` with no build/translate. Otherwise build **once** via `report.build(repo, org_id, self._pivot)`. If that build returns `None`, every requested lang maps to `None` with **no** `translate` calls (nothing to translate). Otherwise, for each `lang`: the pivot's own text when `lang == self._pivot`, else `await self._translator.translate(text, target_lang=lang, source_lang=self._pivot)`.
  - `NativeLocalizer.report_notes`: `{lang: await report.build(repo, org_id, lang) for lang in langs}` — one build per requested lang, each independently possibly `None`; no translation.
  Result keys must equal `langs` exactly in both. Update each method's docstring to state the report shape and the `None`-report edge. Uses only the collaborators the existing constructors already hold (`_translator`, `_pivot`); no constructor change.

### Phase 2: Wire and consume in the report entrypoint (10.2)

- [x] **Task 2: Build the report via the localizer per channel language** (depends on Task 1)
  Files: `scripts/report.py`
  At the composition root, construct the shipping-default localizer alongside the existing wiring:
  `localizer = PivotLocalizer(reasoner, LLMTranslator(llm), pivot=settings.pivot_lang)` (import `PivotLocalizer` from `src.reasoning.localizer` and `LLMTranslator` from `src.reasoning.translator`; reuse the already-built `llm`/`reasoner`).
  In the per-repo loop, replace the direct `text = await report.build(repo, org_id, lang=plan.language)` with:
  `notes = await localizer.report_notes(report, repo, org_id, {plan.language})` then `text = notes.get(plan.language)`.
  Keep the existing `if text is None: … skipped_empty` and `if plan.telegram_channel is None: … skipped_no_channel` branches unchanged — the report path still consumes only `plan.telegram_channel` and `plan.language`. Do not add a parallel localization path; the localizer is the only route. Default channel language stays `"ru"` (unchanged config).

### Phase 3: Tests & verification

- [x] **Task 3: Mandatory call-count test mirroring 8.2.1** (depends on Task 1)
  Files: `tests/reasoning/test_localizer.py`, `tests/reasoning/conftest.py`
  Add a minimal `FakeReport` (in `conftest.py`, structurally satisfying `ReportProtocol`; not a `changelog.Report` import) whose async `build(repo, org_id, lang)` records every `(repo, org_id, lang)` call and returns a deterministic marker such as `f"report:{lang}"`; make its return configurable (e.g. a `result` attribute, default the marker) so a case can force `build` to return `None`. Expose it via a `fake_report` fixture. Add tests reusing `fake_translator`:
  - `PivotLocalizer(pivot="en").report_notes(report, repo, org_id, {"ru","en"})` → `fake_report` built **once** with `lang="en"`; `fake_translator.calls == [("report:en", "ru", "en")]`; `result["en"] == "report:en"`, `result["ru"] == "translated:ru:en"`; `set(result) == {"ru","en"}`.
  - A non-`"en"` pivot case (e.g. `pivot="ru"`, `langs={"en"}`) asserting `source_lang=pivot` is genuinely passed (not the `translate` `"en"` default).
  - `NativeLocalizer.report_notes(report, repo, org_id, {"ru","en"})` → `fake_report` built exactly `len(langs)` times, one per lang; `fake_translator.calls == []`; result keys `== {"ru","en"}`.
  - Empty `langs` for both strategies → `{}` with **zero** builds and zero translates.
  - **`None`-report edge (new behavior, not present in `notes`):** with `fake_report` forced to return `None`, `PivotLocalizer.report_notes(report, repo, org_id, {"ru","en"})` → `{"ru": None, "en": None}` and `fake_translator.calls == []` (a `None` pivot text must never be passed into `translate`); `NativeLocalizer.report_notes(report, repo, org_id, {"ru","en"})` → `{"ru": None, "en": None}` with `fake_translator.calls == []`.
  These pin the silent-failure surfaces: a pivot that quietly builds per language, self-translates its own pivot, or feeds a `None` report text into `translate`, must fail the call-count / value assertions.

- [x] **Task 4: Verify `lang` threading through sections** (depends on Task 2)
  Files: `src/changelog/report.py`, `src/changelog/sections/summary.py`, `src/changelog/sections/per_branch.py`, `src/changelog/sections/remaining.py`
  Confirm `lang` is threaded `report.build` → `section.render` → `narrate`/`prompt.build` in every section (already the case from 10.1.x). This is a read-only verification; make a code change **only** if a section is found to drop `lang` — no speculative edits.
