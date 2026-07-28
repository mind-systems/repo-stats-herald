## Code Review Summary

**Files Reviewed:** plan `41-8-2-2-localizer-translator-impl.md` against `src/reasoning/translator.py`, `src/reasoning/localizer.py`, `src/llm/client.py`, `src/core/config.py`, `scripts/eval.py`, `evals/cases.yaml`, `tests/reasoning/test_localizer.py`, `tests/reasoning/conftest.py`, `src/reasoning/reasoner.py`, `src/reasoning/narration_prompt.py`, `src/episodic/linked_change.py`, `src/knowledge/source_strategy.py`
**Risk Level:** 🟢 Low

Reviewed against the governing spec `.ai-factory/specs/31-localization.md` (named by ROADMAP task 8.2.2) and 8.2.1's red suite `tests/reasoning/test_localizer.py`.

### Context Gates
- **Roadmap:** Plan heading maps cleanly to `ROADMAP.md` task **8.2.2 — Localizer + translator (impl)**, `Spec: .ai-factory/specs/31-localization.md`. All plan tasks trace to spec clauses (LLMTranslator with identifier-preserving prompt, both strategies' dispatch, pivot-as-config, composition-root wiring, eval verification). No gate violation.
- **Architecture:** Plan honors the DI/composition-root rules — `LLMTranslator` takes an `LLMClient` (never `OllamaClient`), concretes wired only in `scripts/eval.py`, prompt text owned by the class, pivot pulled from `Settings` not hardcoded. Consistent with `.ai-factory/ARCHITECTURE.md` and the project CLAUDE.md patterns.
- **Rules:** No violations observed. `pivot_lang` config mirrors `ollama_model` shape; no env read in features; logging setting is "minimal" (Settings: minimal, Docs: no) which matches a pure-impl task.

### Critical Issues

**1. `LocalizeCaseHandler` output ordering is non-deterministic — defeats the eval's diffability guarantee (Task 4, `scripts/eval.py`).**
`notes` returns a dict whose keys are built by iterating the incoming `langs` **set** (both `PivotLocalizer` and `NativeLocalizer` iterate `langs` directly, and the plan feeds the handler `set(inputs["langs"])`). Python randomizes string hashing per process (`PYTHONHASHSEED`), so set iteration order — and therefore the `## <lang>` section order in the joined output — can differ between `make eval` runs. The eval harness's stated purpose is a "stable-named output file per case ... diffable against the references"; unstable section ordering produces noisy diffs against the user-authored `evals/reference/<case>.md` and undermines the very verification this task exists to enable.
*Fix:* have `LocalizeCaseHandler.run` render sections in a deterministic order — iterate `sorted(notes)` (or `sorted(inputs["langs"])`) when building the `## <lang>` blocks. This is presentation logic that belongs in the handler, so it needs no change to the localizer contract or 8.2.1's tests (which assert only key sets, never order).

### Minor Issues

**2. Range-splitting is implied but not spelled out (Task 4, `scripts/eval.py`).**
`LinkedChangeResolver.resolve` takes `(repo, before, after)`, not a `range` string. The plan says the handler "resolves a `LinkedChange` from a `range`" — the implementer must split `inputs["range"]` into `before/after` first, exactly as `NarrateCaseHandler._split_range` already does. Not a defect (the plan points at the existing narrate handler as the template), but worth stating explicitly so the split step isn't missed.

### Positive Notes
- **Dispatch spec is exact and test-faithful.** Task 2's description of both strategies (pivot narrated exactly once even when not requested, `source_lang=self._pivot`, pivot placed raw only when in `langs`, empty-`langs` short-circuit with zero calls, keys == `langs`) matches every assertion in `tests/reasoning/test_localizer.py` — including the non-`"en"` pivot case and the `sorted(...)` argument-tuple checks. No new dispatch behavior is introduced beyond what 8.2.1 pinned.
- **`StubTranslator` deletion is safe.** Confirmed no code imports it — the only references outside `translator.py` are plan files. Task 1's "confirm no other module imports it" holds.
- **DI discipline correct.** `LLMTranslator(LLMClient)`, `OllamaClient` wired only at the eval root, prompt as an owned module-level template rendered by a private method — mirrors `Summarizer`/`OllamaClient`/`PromptBuilder` precisely, and the `Translator` ABC names no backend (spec guard satisfied).
- **Config addition is right-shaped.** `pivot_lang: str = "en"` next to `reasoner_k` needs no validator (plain string, same as `ollama_model`) — correctly identified.
- **Eval wiring reuses the existing branch.** Extending the `if any(case.type in (...))` guard to include `"localize"` and building the translator/localizer inside the pool/`reasoner` branch reuses the already-constructed `reasoner` and pool — no duplicate infra.
- **Reference-file discipline respected.** Task 4 correctly instructs adding only the case (never fabricating `evals/reference/<case>.md`), matching the discipline in `cases.yaml`'s existing comments and project CLAUDE.md.

The plan is well-grounded in the codebase and faithful to the spec; only issue #1 needs addressing before implementation to keep the eval verification meaningful.
