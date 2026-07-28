## Code Review Summary

**Files Reviewed:** plan `41-8-2-2-localizer-translator-impl.md` against `src/reasoning/translator.py`, `src/reasoning/localizer.py`, `src/reasoning/reasoner.py`, `src/reasoning/narration_prompt.py`, `src/summarization/prompt.py`, `src/llm/client.py`, `src/core/config.py`, `scripts/eval.py`, `evals/cases.yaml`, `tests/reasoning/test_localizer.py`, `tests/reasoning/conftest.py`, `src/episodic/linked_change.py`
**Risk Level:** 🟢 Low

Reviewed against the governing spec `.ai-factory/specs/31-localization.md` (named by `ROADMAP.md` task 8.2.2) and 8.2.1's red suite `tests/reasoning/test_localizer.py`. This is round 2; both issues raised in review-1 are resolved (see below).

### Context Gates
- **Roadmap:** Plan heading maps cleanly to `ROADMAP.md` task **8.2.2 — Localizer + translator (impl)**, `Spec: .ai-factory/specs/31-localization.md`. Every plan task traces to a spec clause: `LLMTranslator` with identifier-preserving prompt (Change bullet 1 + Guard 3), both strategies' dispatch (Change bullet 2), pivot-as-config passed as `source_lang` (Guard 2), narration-primitive guard (Guard 4), composition-root wiring + eval verification (Verification). No gate violation.
- **Architecture:** Honors the DI / composition-root rules in `.ai-factory/ARCHITECTURE.md` and the project CLAUDE.md — `LLMTranslator(Translator)` takes an `LLMClient` (never `OllamaClient`), concretes wired only at the `scripts/eval.py` root, prompt text owned as a module-level template rendered by a private method (mirroring `PromptBuilder`/`NarrationPromptBuilder`/`OllamaClient`), and `pivot_lang` pulled from `Settings` rather than hardcoded. No boundary/dependency violation.
- **Rules:** `.ai-factory/RULES.md` carries no counter-defaults; nothing to enforce. `pivot_lang: str = "en"` mirrors `ollama_model`'s shape (no validator needed), features read no env directly, and the "minimal logging / no docs / no tests" settings match a pure-impl task greening an existing red suite.

### Verification against ground truth
- **Dispatch matches the pinned tests exactly.** Task 2's spec of both strategies — pivot narrated exactly once even when not among `langs`, `translate(narration, target_lang=lang, source_lang=self._pivot)` for every non-pivot lang, pivot placed raw only when itself requested, empty-`langs` short-circuit with zero calls, result keys == `langs` — reproduces every assertion in `tests/reasoning/test_localizer.py`, including the non-`"en"` pivot case (`test_..._uses_configured_pivot_as_source_lang`) and the `sorted(...)` argument-tuple checks. No dispatch behavior beyond what 8.2.1 pinned.
- **`StubTranslator` deletion is safe.** Confirmed by grep: the only reference outside `translator.py` is a stale `.pyc` cache; `localizer.py` and `conftest.py` import the `Translator` ABC, never the stub. Task 1's "confirm no other module imports it" holds.
- **API signatures are correct.** `LinkedChangeResolver.resolve(repo, before, after)` takes three args, not a range string — the plan correctly requires splitting `inputs["range"]` first, reusing `NarrateCaseHandler._split_range`'s `rsplit("..", 1)`. `OllamaClient(base_url, model, api_key, …)` matches the wiring the plan prescribes. `Reasoner.narrate(change, lang)` and `Translator.translate(text, target_lang, source_lang)` match the calls in Task 2.
- **Eval wiring reuses the existing branch.** Extending the `if any(case.type in ("reasoner", "narrate"))` guard to include `"localize"` and building the translator/localizer inside that pool/`reasoner` branch reuses the already-constructed `reasoner` and pool — no duplicate infra. The chosen case (`langs: [en, ru]`, pivot `en`) genuinely exercises translation: `en` is placed raw and `ru` is translated from the `en` narration, satisfying the Verification bullet.
- **Determinism guarantee is real.** `notes` returns a dict keyed by iterating the `langs` **set**; `sorted(notes)` in the handler is what pins `## <lang>` section order across `PYTHONHASHSEED`-randomized runs, keeping `evals/out/<case>.md` diffable against a user-authored reference. This is presentation logic in the handler and touches neither the localizer contract nor 8.2.1's order-agnostic tests.

### Prior-review issues — resolved
- **review-1 #1 (non-deterministic output ordering):** Resolved. Task 4 now mandates `sorted(notes)` when rendering the `## <lang>` blocks, with the `PYTHONHASHSEED` rationale spelled out.
- **review-1 #2 (range-splitting left implicit):** Resolved. Task 4 now explicitly reuses the `rsplit("..", 1)` logic from `NarrateCaseHandler._split_range` and states that `LinkedChangeResolver.resolve` takes `(repo, before, after)`.

### Critical Issues
None.

### Positive Notes
- **DI discipline is exact.** `LLMTranslator(LLMClient)`, `OllamaClient` wired only at the eval root, prompt as an owned module-level template — the `Translator` ABC names no backend, so the spec's "a dedicated MT service swaps in later" guard is honored.
- **Narration primitive preserved.** Both strategies route through `Reasoner.narrate`; neither reimplements generation (Guard 4 satisfied).
- **Prompt-style guidance is grounded.** Task 1 points the translation prompt at the existing plain-text style of `src/summarization/prompt.py` / `src/reasoning/narration_prompt.py` (module-level template + private render method), which is the actual pattern in those files.
- **Reference-file discipline respected.** Task 4 adds only the case and explicitly forbids fabricating `evals/reference/<case>.md`, matching `cases.yaml`'s existing comments and the project CLAUDE.md eval discipline.
- **No migration needed and none invented.** `pivot_lang` is plain config; there is no schema change, and the plan correctly adds nothing to the pgvector schemas.

The plan is well-grounded in the codebase, faithful to the spec and to 8.2.1's pinned dispatch, and both round-1 findings are closed. No changes required before implementation.

PLAN_REVIEW_PASS
