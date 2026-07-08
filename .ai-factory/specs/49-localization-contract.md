# 8.2.1 — Localization contract (red tests)

**Phase:** 8 — Narration (the broadcast projection). Depends on 8.1 (`Reasoner.narrate`), Phase 1 (`LLMClient`). First half of the localization milestone — the two ABCs + dispatch invariants, pinned with red tests, ahead of the real translation implementation (8.2.2).

## Current state

`Reasoner.narrate(change, lang)` (8.1) produces narration in one language natively per call. Multi-language consumers — release notes (11.2), the daily and weekly reports (10.x) — need a note per required language, and the language-generation strategy (native per language vs. one canonical language translated) is a model-tier concern: a smaller model reasons best in one language and translates from it, while a stronger model may generate each language natively. Nothing today chooses between these strategies, and nowhere is that choice made swappable.

The dispatch between the two strategies is itself a silent-failure surface: a `PivotLocalizer` implementation that quietly calls `narrate` per language (instead of once, translating the rest) defeats the whole point of choosing "pivot" — no exception, just a wrong strategy silently running under the pivot's name. A `PivotLocalizer` that self-translates its own pivot language wastes an LLM call and risks corrupting identifiers/proper nouns through a pointless round-trip. A `NativeLocalizer` that under- or over-calls `narrate` silently under- or over-produces the requested languages.

## Change

Define `Translator` and `Localizer`'s shapes, and pin each strategy's call-count dispatch with red tests over mocked collaborators — before writing the real translation prompt (which stays a genuine LLM-output-quality concern, unchanged, and lands in 8.2.2).

- `src/reasoning/translator.py` — `Translator` (ABC): `translate(text: str, target_lang: str, source_lang: str = "en") -> str`. Names no concrete backend. A STUB implementation raises for now.
- `src/reasoning/localizer.py` — `Localizer` (ABC): `notes(change: LinkedChange, langs: set[str]) -> dict[str, str]`.
  - `PivotLocalizer(Localizer)` — constructed with `(reasoner, translator, pivot: str = "en")` (STUBBED `notes`, raises for now).
  - `NativeLocalizer(Localizer)` — constructed with `(reasoner)` (STUBBED `notes`, raises for now).
- Write red tests over **mocked `reasoner.narrate`** and **mocked `translator.translate`** pinning:
  - `PivotLocalizer.notes(change, {"ru", "en"})` (pivot `"en"`) → exactly **one** `narrate(change, "en")` call, plus exactly `len(langs) - 1` `translate(...)` calls (one per non-pivot language); the pivot language's entry in the returned dict is the raw `narrate` output, never passed through `translate`;
  - `NativeLocalizer.notes(change, {"ru", "en"})` → exactly `len(langs)` `narrate` calls, one per language in `langs`, each with the matching `lang` argument;
  - both strategies' returned dict has exactly the keys in `langs`, no more, no fewer.

## Files & types

- new `src/reasoning/translator.py` (`Translator` ABC + stub)
- new `src/reasoning/localizer.py` (`Localizer` ABC, `PivotLocalizer`/`NativeLocalizer` stubs)
- new test file(s) covering the dispatch cases above, run against mocked `narrate`/`translate` (red)

## Guards

- Tests-first: both strategies' stubs raise — 8.2.2 turns these tests green, never redesigns the dispatch.
- Both strategies sit behind **one** `Localizer` seam — callers call only `notes(change, langs)` and never know which strategy backs it.
- The call-count/argument assertions run against **mocks only** — no real `LLMClient`. Whether the translated text actually preserves identifiers and reads naturally is 8.2.2's eval-harness concern, not asserted here.

## Verification

- The test suite added here is red against the stubs (fails only because `notes` has no dispatch logic yet).
- Each of the pinned cases (`PivotLocalizer`'s 1-narrate-plus-(n-1)-translate split with an untranslated pivot, `NativeLocalizer`'s n-narrate dispatch, exact-key-set results for both) has a corresponding red test.
