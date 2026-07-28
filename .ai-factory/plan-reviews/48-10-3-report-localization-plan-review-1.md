## Code Review Summary

**Plan:** `48-10-3-report-localization.md` (task 10.3 — Report localization)
**Files Reviewed:** plan + targeted code (`src/reasoning/localizer.py`, `src/reasoning/translator.py`, `src/changelog/report.py`, `src/changelog/sections/*`, `scripts/report.py`, `scripts/eval.py`, `src/core/config.py`, `src/routing/resolver.py`, `tests/reasoning/{conftest,test_localizer}.py`) + governing spec `.ai-factory/specs/39-weekly-digest-localization.md`
**Risk Level:** 🟢 Low

### Context Gates
- **Roadmap (ROADMAP.md:102):** WARN-clear. Plan title matches task 10.3 exactly; the task's `Spec:` points at `.ai-factory/specs/39-weekly-digest-localization.md`, which the plan honors. Linkage intact.
- **Governing spec (39):** Plan conforms to the Change, Files & types, and Guards sections. The mandatory call-count tests (Task 3) mirror the spec's required set (pivot builds once + N−1 translate; native builds `len(langs)` times; empty → zero builds). ✔
- **Architecture (ARCHITECTURE.md:41–42) / ROADMAP:100 guard `changelog → reasoning` one-way:** PASS. The plan correctly refuses to import `Report` from `changelog` into `reasoning`, typing the argument via a structural `ReportProtocol(typing.Protocol)` declared inside `reasoning`. This is the single most important correctness point of the task and the plan gets it right. The composition root (`scripts/report.py`, which may import both features) passes the concrete `Report`, which structurally satisfies the Protocol.
- **RULES.md / skill-context:** No `.ai-factory/skill-context/aif-review/SKILL.md` present — no project overrides to apply.

### Verified assumptions (all correct)
- `Report.build(self, repo, org_id, lang="ru") -> str | None` (report.py:77) exactly matches the `ReportProtocol.build` signature the plan declares. ✔
- `PivotLocalizer.__init__(reasoner, translator, pivot="en")` holds `_translator`/`_pivot`; `report_notes` needs no constructor change. ✔ (Note: `_reasoner` is unused by `report_notes` — harmless, and matches the eval-precedent wiring shape.)
- `Translator.translate(text, target_lang, source_lang="en")` (translator.py:23) — the non-`"en"` pivot test genuinely exercises `source_lang=pivot` vs the default. ✔
- Wiring precedent `PivotLocalizer(reasoner, LLMTranslator(llm), pivot=settings.pivot_lang)` exists at scripts/eval.py:230–233; `settings.pivot_lang` defaults to `"en"` (config.py:47). ✔ `llm` (report.py:61) and `reasoner` (report.py:63) are both in scope at the replacement site.
- `plan.language` defaults to `"ru"` (routing/resolver.py:27), unchanged. ✔
- Adding an `@abstractmethod report_notes` to `Localizer` breaks no other subclass: only `PivotLocalizer`/`NativeLocalizer` subclass it (both get impls); `LocalizeCaseHandler` and tests only *use* a `Localizer`, never subclass it. ✔
- **Task 4 is correctly a read-only verification, not an edit.** `lang` already threads `report.build` → `section.render(…, lang)` → `narrate(change, lang)` / `remaining_prompt.build(tasks, lang)` in all three sections (summary.py:41, per_branch.py:63, remaining.py:71). The spec's "edit sections to thread `lang`" is already satisfied from 10.1.x; the plan's downgrade to verify-only is a correct, ground-truth-based deviation. ✔

### Critical Issues
None. The plan is implementable as written and architecturally sound.

### Findings

1. **[LOW · test-coverage] The `None`-report edge the plan itself elevates to a first-class silent-failure surface is left untested.** Task 1 introduces genuinely new behavior absent from `notes`: when `report.build` returns `None`, `PivotLocalizer.report_notes` must map every lang to `None` with **zero** `translate` calls, and `NativeLocalizer` maps each lang to `None`. The plan explicitly calls this out ("`notes` never faces a `None` narration, so `report_notes` must define this edge explicitly"). Yet Task 3's `FakeReport` returns a deterministic non-`None` marker (`f"report:{lang}"`), so the `None` branch is never exercised. This is exactly a silent-failure surface (a wrong impl would pass `None` text into `translate` and quietly get garbage, not crash) — the class of thing the plan's own call-count tests exist to pin. It is within the task's scope (same file, `tests/reasoning/test_localizer.py` / `conftest.py`) and fixable in the next iteration. Recommend adding one case per strategy: a `FakeReport` configured to return `None`, asserting Pivot → `{lang: None for lang in langs}` and `fake_translator.calls == []`, and Native → `{lang: None …}` with no translate.

### Positive Notes
- Structural-Protocol approach to keep `reasoning` free of a `changelog` import is the correct resolution of the one-way dependency guard — and the plan states the reasoning explicitly rather than leaving it implicit.
- `report_notes` return type widened to `dict[str, str | None]` is an honest, ground-truth-driven refinement of the spec's illustrative `dict[str, str]`: `Report.build` really can return `None`, unlike `narrate`.
- Task 2 preserves the existing `skipped_empty` / `skipped_no_channel` control flow untouched and routes solely through the localizer (no parallel path), satisfying the spec's "no parallel localization path" guard.
- Grounding notes cite real line anchors and the eval-precedent wiring; the tasks are ordered with correct dependencies (Task 2 & 3 depend on Task 1; Task 4 on Task 2).

## Deferred observations
- Affects: Phase 11 (`11.2.2` / `11.3`, specs `20-release-note.md`, `21-github-release.md`) — Widening `report_notes` to `dict[str, str | None]` ripples to future consumers that index the result directly (`notes[plan.language]`, `notes[plan.github_release_language]`) and today assume a usable string. Those phase-11 call sites will need to handle a possibly-`None` note (empty report → no release body / no Telegram send). Out of this task's file boundary; flagged for whoever implements the release path so the `None` case is not silently formatted as the literal `"None"`.
- Affects: Verification / eval harness — With `PivotLocalizer(pivot="en")` as the shipping default (established at 8.2.2 and mirrored here), a `"ru"` channel's report is now generated natively in English and then machine-translated to Russian, rather than built natively in Russian as `report.build(lang="ru")` did before. This mirrors the already-accepted narration path and stays within the pivot architecture's intent (the spec's "default `"ru"` output unchanged" reads as *language selection* unchanged, not byte-identical text), so it is not a plan defect — but the translated-report quality for the default channel is a real behavioral change worth confirming through the eval `localize` handler rather than assuming parity.
