# Plan: 8.2.2 — Localizer + translator (impl)

## Context
Turn 8.2.1's red dispatch tests green by implementing `PivotLocalizer.notes`/`NativeLocalizer.notes` and the LLM-backed `LLMTranslator`, then wire `PivotLocalizer` as the shipping default at the eval composition root with the pivot language as config — verifying translation quality (identifiers/proper nouns preserved, meaning intact) through the eval harness.

## Settings
- Testing: no
- Logging: minimal
- Docs: no

## Tasks

### Phase 1: Implementation (greens 8.2.1)

- [x] **Task 1: Implement `LLMTranslator`**
  Files: `src/reasoning/translator.py`
  Replace the `StubTranslator` placeholder with `LLMTranslator(Translator)`. Constructor injects an `LLMClient` (the abstraction from `src/llm/client.py`), never a concrete backend — mirroring `Summarizer`/`Reasoner`. Keep the `Translator` ABC and its signature `translate(self, text, target_lang, source_lang="en")` unchanged.
  - `translate` builds a translation prompt from `text`, `source_lang`, `target_lang` and calls `await self._llm.generate(prompt)`, returning the result.
  - The prompt is an owned detail of this class (like `OllamaClient`'s HTTP specifics / `PromptBuilder`'s prompt text): a module-level template string rendered by a small private method. Instruct the model to translate `text` from `source_lang` into `target_lang` while **preserving identifiers and proper nouns untranslated** — feature names, repository names, code symbols read the same across languages — and to return only the translated prose (no preamble). Use plain-text prompt style consistent with `src/summarization/prompt.py` and `src/reasoning/narration_prompt.py`.
  - Delete `StubTranslator` (its only referent is the raising stub the tests supersede); confirm no other module imports it.

- [x] **Task 2: Implement `PivotLocalizer.notes` and `NativeLocalizer.notes`**
  Files: `src/reasoning/localizer.py`
  Replace both raising `notes` bodies with real dispatch; keep the `Localizer` ABC, both constructors, and all class docstrings unchanged.
  - `NativeLocalizer.notes`: for each `lang` in `langs`, `await self._reasoner.narrate(change, lang)`; return `{lang: narration}`. Empty `langs` → `{}` with zero `narrate` calls. Never calls the translator (it has none).
  - `PivotLocalizer.notes`: if `langs` is empty, return `{}` without narrating or translating (the pivot is never generated speculatively). Otherwise call `await self._reasoner.narrate(change, self._pivot)` **exactly once**, then for every `lang in langs`: if `lang == self._pivot`, place the raw narration under that key; else `await self._translator.translate(narration, target_lang=lang, source_lang=self._pivot)` — the configured `pivot` is passed as `source_lang`, so a non-`"en"` pivot is never read as `"en"`. Result keys equal `langs` exactly. When the pivot is not among `langs`, it is still narrated once as the intermediate but does not appear in the result.
  - Guard: neither strategy reimplements narration — both go through `Reasoner.narrate` (8.1), the single native-generation primitive.
  - This is behavior-preserving against 8.2.1's `tests/reasoning/test_localizer.py` — introduce no dispatch behavior the tests do not already pin (call counts, argument tuples, exact key sets). Run `uv run pytest tests/reasoning/test_localizer.py` to confirm the suite is green.

### Phase 2: Composition-root wiring & eval verification

- [x] **Task 3: Add pivot-language config** (depends on Task 2)
  Files: `src/core/config.py`
  Add `pivot_lang: str = "en"` to `Settings` (placed with the other reasoning/narration settings such as `reasoner_k`). This is the configurable pivot the composition root injects into `PivotLocalizer`; features never hardcode `"en"`. No validator needed (plain string, same shape as `ollama_model`).

- [x] **Task 4: Wire `PivotLocalizer` at the eval composition root + register a `localize` eval handler** (depends on Task 1, Task 2, Task 3)
  Files: `scripts/eval.py`, `evals/cases.yaml`
  Wire the localization slice at the eval composition root (the same one that already wires `narrate`) so translation quality is verifiable end-to-end.
  - In `scripts/eval.py`, import `LLMTranslator`, `PivotLocalizer` from `src.reasoning.*`. Inside the `reasoner`/`narrate` branch (which already builds a `Reasoner` and a pool), construct `LLMTranslator(OllamaClient(...))` and `PivotLocalizer(reasoner, translator, pivot=settings.pivot_lang)` — `PivotLocalizer` is the shipping default (`NativeLocalizer` is not wired here; swapping the strategy is a one-line composition-root change with zero caller edits).
  - Add a `LocalizeCaseHandler(CaseHandler)` (alongside `NarrateCaseHandler`) that: splits `inputs["range"]` into `before`/`after` (reuse the same `rsplit("..", 1)` logic `NarrateCaseHandler._split_range` uses — `LinkedChangeResolver.resolve` takes `(repo, before, after)`, not a range string), resolves a `LinkedChange` via the existing `LinkedChangeResolver(GitCommitCollector(), AiFactorySourceStrategy())`, calls `await self._localizer.notes(change, set(inputs["langs"]))`, and returns the per-language notes joined into one readable text (a `## <lang>` heading per language followed by its note). **Render sections in a deterministic order — iterate `sorted(notes)` (not raw dict/set iteration order) when building the `## <lang>` blocks**, so the output file is stable across runs and diffs cleanly against the user-authored reference. `PYTHONHASHSEED` randomizes set/dict-key iteration per process, so sorting is what makes the eval's diffability guarantee hold; this is presentation logic in the handler and needs no change to the localizer contract or 8.2.1's tests (which assert only key sets, never order). Register it under the `"localize"` key; extend the `if any(case.type in (...))` guard so the pool/reasoner branch also triggers for `"localize"` cases.
  - In `evals/cases.yaml`, add one `type: localize` case over this repo (e.g. `repo: .`, `range: HEAD~3..HEAD`, `langs: [en, ru]`) with a pivot of `en` so `ru` is genuinely translated from the `en` narration. Add a short comment mirroring the existing cases: the comparison reference `evals/reference/<case>.md` is **user-authored — never fabricated by the implementer**, same discipline as the summarization/narrate evals. Do NOT create the reference file.
  - The eval confirms the Verification bullet: for a fixed case, `ru` is translated from the `en` narration with identifiers/proper nouns preserved and the pivot's meaning intact. Run via `make eval` (needs the SSH tunnel + populated stores, per project CLAUDE.md) when validating; the harness writes `evals/out/<case>.md`.
