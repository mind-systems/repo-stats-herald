# Plan: 8.2.1 — Localization contract (red tests)

## Context
Define the `Translator` and `Localizer` ABCs plus the `PivotLocalizer`/`NativeLocalizer` strategy stubs (raising for now), and pin each strategy's `narrate`/`translate` call-count dispatch with red tests over mocked collaborators — ahead of the real implementation in 8.2.2.

## Settings
- Testing: yes
- Logging: minimal
- Docs: no

## Tasks

### Phase 1: Contract abstractions & stubs

- [x] **Task 1: Define the `Translator` ABC + raising stub**
  Files: `src/reasoning/translator.py`
  Add `Translator(ABC)` with one abstract coroutine `translate(self, text: str, target_lang: str, source_lang: str = "en") -> str`. Follow the ABC style in `src/llm/client.py` (`from abc import ABC, abstractmethod`; `async def ... -> str: ...`). The signature names no concrete backend (no Ollama/MT-service concept) — the swap seam is the same abstraction discipline as `LLMClient`. Add a concrete `StubTranslator(Translator)` whose `translate` raises `NotImplementedError` (the real `LLMTranslator` lands in 8.2.2). Keep the class docstring behavioral (what the seam is for — reason-in-one-language-and-translate-the-rest), not a method list.

- [x] **Task 2: Define the `Localizer` ABC + `PivotLocalizer`/`NativeLocalizer` stubs** (depends on Task 1)
  Files: `src/reasoning/localizer.py`
  Add `Localizer(ABC)` with one abstract coroutine `notes(self, change: LinkedChange, langs: set[str]) -> dict[str, str]` (import `LinkedChange` from `src/episodic/linked_change.py`). Add two concrete subclasses, both with `notes` stubbed to raise `NotImplementedError` (greened in 8.2.2, which must not redesign the dispatch):
  - `PivotLocalizer(Localizer)` — constructor `(self, reasoner: Reasoner, translator: Translator, pivot: str = "en")`, storing each on a private attribute. Import `Reasoner` from `src/reasoning/reasoner.py` and `Translator` from `src/reasoning/translator.py`. Docstring pins the intended dispatch for the implementer: narrate the pivot **once**, then `translate` every requested language except the pivot with `source_lang=` the configured `pivot`; the pivot's own narration is returned untranslated and only when the pivot is itself requested.
  - `NativeLocalizer(Localizer)` — constructor `(self, reasoner: Reasoner)`. Docstring pins: one `narrate` call per language in `langs`, each with the matching `lang`.
  Both strategies sit behind the single `Localizer.notes` seam — callers never know which strategy backs them. Empty `langs` is documented as a valid input yielding an empty dict with zero collaborator calls.

### Phase 2: Red dispatch tests

- [x] **Task 3: Add mock collaborators for `narrate`/`translate`** (depends on Task 2)
  Files: `tests/reasoning/conftest.py`
  Extend the existing `tests/reasoning/conftest.py` with two lightweight recording fakes and fixtures, mirroring the recording-fake style already there (`FakeLLMClient`, `FakeEmbedder`):
  - `FakeNarratingReasoner` — records every `narrate(change, lang)` call (append `(change, lang)` to a `calls` list) and returns a deterministic per-lang marker such as `f"narrated:{lang}"`. It only needs to satisfy the `narrate` surface the localizers call (not the full `Reasoner`), so implement it as a minimal stand-in rather than subclassing `Reasoner`.
  - `FakeTranslator(Translator)` — records every `translate(text, target_lang, source_lang)` call (append the full tuple to a `calls` list) and returns a deterministic marker such as `f"translated:{target_lang}:{source_lang}"`.
  Add `pytest` fixtures `fake_narrating_reasoner` and `fake_translator` returning fresh instances. Reuse the module's existing `_make_change`-style `LinkedChange` construction pattern (see `tests/reasoning/test_narrate.py`) for building the `change` argument, or add a shared helper.

- [x] **Task 4: Pin `PivotLocalizer` dispatch (pivot requested + pivot not requested)** (depends on Task 3)
  Files: `tests/reasoning/test_localizer.py`
  New test file. Over the mocked collaborators, assert (tests are RED against the raising stubs):
  - `PivotLocalizer(reasoner, translator, pivot="en").notes(change, {"ru", "en"})` → exactly **one** `narrate(change, "en")` call; exactly one `translate` call, for `"ru"`, with `source_lang="en"` (never relying on `translate`'s `"en"` default — assert the passed `source_lang` explicitly so a non-`"en"` pivot cannot be silently read as `"en"`); the returned dict's `"en"` entry is the raw `narrate` output (never routed through `translate`).
  - `PivotLocalizer(..., pivot="en").notes(change, {"ru", "de"})` (pivot **not** requested) → still exactly **one** `narrate(change, "en")`; exactly **two** `translate` calls (`"ru"`, `"de"`), each `source_lang="en"`; result keys exactly `{"ru", "de"}` — the pivot `"en"` is generated as the intermediate but **not** present in the result.
  Prefer a non-`"en"` pivot in at least one assertion path (e.g. a `pivot="ru"` case) so the `source_lang=pivot` wiring is genuinely exercised, not passed by coincidence with the default.

- [x] **Task 5: Pin `NativeLocalizer` dispatch, empty-langs, and exact-key-set for both strategies** (depends on Task 3)
  Files: `tests/reasoning/test_localizer.py`
  In the same new test file, assert:
  - `NativeLocalizer(reasoner).notes(change, {"ru", "en"})` → exactly `len(langs)` `narrate` calls, one per language in `langs`, each with the matching `lang` argument (assert the set of `lang` arguments equals `langs`); **zero** `translate` involvement (native has no translator).
  - Empty `langs`: both `PivotLocalizer.notes(change, set())` and `NativeLocalizer.notes(change, set())` → an empty dict and **zero** `narrate`/`translate` calls (Pivot must not narrate the pivot when nothing is requested).
  - Exact key set: both strategies' returned dict has keys equal to `langs` exactly — no extra pivot key, none missing.
  Keep call-count/argument assertions against the mocks only — no real `LLMClient`; translation text quality is 8.2.2's eval-harness concern, not asserted here.
