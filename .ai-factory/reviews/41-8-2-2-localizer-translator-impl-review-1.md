## Code Review — 8.2.2 Localizer + translator (impl)

**Files reviewed (in full):** `src/reasoning/translator.py`, `src/reasoning/localizer.py`, `src/core/config.py`, `scripts/eval.py`, `evals/cases.yaml` — cross-checked against `src/reasoning/reasoner.py`, `src/reasoning/narration_prompt.py`, `src/summarization/prompt.py`, `src/llm/client.py`, `src/episodic/linked_change.py`, `tests/reasoning/test_localizer.py`, `tests/reasoning/conftest.py`, and the governing spec `.ai-factory/specs/31-localization.md`.

**Risk Level:** 🟢 Low

### Verification run
- `uv run pytest tests/reasoning/test_localizer.py` → **8 passed** (8.2.1's red suite is now green).
- `uv run pytest` (full suite) → **104 passed**, no regressions.
- `import scripts.eval` → succeeds; the new imports and `LocalizeCaseHandler` wiring parse and load cleanly.
- `grep StubTranslator **/*.py` → no matches; the deleted stub has no surviving referent.

### Correctness

- **`LLMTranslator` (translator.py).** Injects `LLMClient` (never a concrete backend), builds the prompt via a module-level template rendered by a private `_build_prompt`, and returns `await self._llm.generate(prompt)`. Matches `Summarizer`/`OllamaClient` DI discipline and the spec guard "`Translator` names no concrete backend." The prompt instructs identifier/proper-noun preservation and "return only the translated text," satisfying Change bullet 1 + Guard 3.
  - Prompt-injection / format safety: `str.format(text=…, target_lang=…, source_lang=…)` only interpolates the template's own placeholders; brace characters inside the substituted `text` (e.g. code snippets in a narration) are NOT re-parsed, so no `KeyError`/`IndexError` from `{}` in the narration. Safe.

- **`PivotLocalizer.notes` (localizer.py).** Empty `langs` → `{}` with zero collaborator calls (pivot never generated speculatively). Otherwise `narrate(change, self._pivot)` exactly once; each requested lang gets the raw narration when `lang == pivot`, else `translate(narration, target_lang=lang, source_lang=self._pivot)`. The configured pivot flows into `source_lang`, so a non-`"en"` pivot is never read as `"en"` (Guard 2). Result keys == `langs`. Reproduces every assertion in `test_localizer.py`, including the positional-text + keyword-arg tuple the `FakeTranslator` records and the non-`"en"` pivot case.

- **`NativeLocalizer.notes`.** `{lang: await narrate(change, lang) for lang in langs}` — one narrate per language, no translator, empty `langs` → `{}`. Correct. Both strategies route generation solely through `Reasoner.narrate` (Guard 4 — no reimplemented narration).

- **`Settings.pivot_lang` (config.py).** `pivot_lang: str = "en"` alongside `reasoner_k`; plain string, no validator needed, mirrors `ollama_model`. No schema/migration implicated, and none was added.

- **Eval wiring (eval.py + cases.yaml).** `LocalizeCaseHandler` splits `inputs["range"]` via its own `rsplit("..", 1)` (correct — `LinkedChangeResolver.resolve` takes `(repo, before, after)`, not a range string), resolves the change, and renders `## <lang>` sections in `sorted(notes)` order — deterministic across `PYTHONHASHSEED`-randomized set iteration, so `evals/out/herald-localize.md` stays diffable against a user-authored reference (both round-1 findings closed). `PivotLocalizer` is wired as the shipping default with `pivot=settings.pivot_lang`; the `if any(case.type in (...))` guard now includes `"localize"`, reusing the already-built pool/`reasoner`. The added case (`langs: [en, ru]`, pivot `en`) genuinely exercises translation (`en` raw, `ru` translated from it). Reference file correctly NOT fabricated.

### Notes (non-blocking)
- `LocalizeCaseHandler` and `NarrateCaseHandler` each construct their own `LinkedChangeResolver(GitCommitCollector(), AiFactorySourceStrategy())`. Minor duplication, consistent with the file's existing composition-root style; not a defect.
- The `localize` case requires populated Postgres stores + the SSH tunnel to run end-to-end, same as the `reasoner`/`narrate` cases — a runtime prerequisite documented in the plan/CLAUDE.md, not a code issue.

No correctness, security, or runtime-breakage issues found. Implementation is faithful to the spec and to 8.2.1's pinned dispatch; the plan-review findings are resolved in the code.

REVIEW_PASS
