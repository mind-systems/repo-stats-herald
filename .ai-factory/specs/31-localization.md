# 8.2.2 — Localizer + translator (impl)

**Phase:** 8 — Narration (the broadcast projection). Depends on 8.2.1 (the `Translator`/`Localizer` ABCs and their call-count dispatch tests). Second half of the localization milestone — turns 8.2.1's dispatch tests green and adds the real translation logic.

## Current state

8.2.1 defines `Translator` and `Localizer`'s shapes, and pins both strategies' dispatch (`PivotLocalizer`'s one-narrate-plus-translate-the-rest split with an untranslated pivot; `NativeLocalizer`'s one-narrate-per-language) with red tests over mocked collaborators. The stubs raise for every call — no real translation prompt, no composition-root wiring exists yet.

## Change

Implement the real per-strategy logic and the LLM-backed translator, using 8.2.1's dispatch mechanics unchanged.

- `src/reasoning/translator.py` — `LLMTranslator(Translator)`: uses the injected `LLMClient` with a translation prompt that preserves identifiers and proper nouns (feature names, repo names) untranslated.
- `src/reasoning/localizer.py`:
  - `PivotLocalizer.notes`: calls `reasoner.narrate(change, pivot)` once, then `translator.translate(..., target_lang)` for every other language in `langs` — reusing 8.2.1's dispatch counting unchanged.
  - `NativeLocalizer.notes`: calls `reasoner.narrate(change, lang)` once per language in `langs` — reusing 8.2.1's dispatch counting unchanged.
- Wired at the composition root: which `Localizer` implementation (and the pivot language, where `PivotLocalizer` is chosen) is a configuration/tier choice — `PivotLocalizer` is the shipping default.

## Files & types

- edit `src/reasoning/translator.py` (stub → `LLMTranslator` implementation)
- edit `src/reasoning/localizer.py` (stubs → `PivotLocalizer`/`NativeLocalizer` implementations)

## Guards

- `Translator` names no concrete backend — a dedicated MT service can replace `LLMTranslator` without touching `Localizer` or its callers.
- The pivot language is configuration (`PivotLocalizer`'s `pivot`, default `"en"`), never hardcoded in callers.
- Translation preserves identifiers/proper nouns — a feature or repo name reads the same across languages.
- `Reasoner.narrate` (8.1) stays the single native-generation primitive — both `PivotLocalizer` and `NativeLocalizer` call it; neither reimplements narration.
- Turns 8.2.1's tests green — introduces no new dispatch behavior beyond what 8.2.1 already pinned.

## Verification

- 8.2.1's red test suite passes green against this implementation.
- `notes(change, {"ru", "en"})` via `PivotLocalizer` (pivot `"en"`) → both languages present in the result, `"ru"` genuinely translated from the `"en"` narration.
- `notes(change, {"ru", "en"})` via `NativeLocalizer` → both languages present, each independently narrated.
- Swapping the composition root's `Localizer` implementation changes the strategy with zero changes to any caller.
- Run through **the eval harness**: translated output for a fixed case preserves identifiers/proper nouns and keeps the meaning of the pivot narration intact.
