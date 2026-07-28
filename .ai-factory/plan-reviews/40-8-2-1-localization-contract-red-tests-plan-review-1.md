## Code Review Summary

**Files Reviewed:** 1 plan (`40-8-2-1-localization-contract-red-tests.md`), verified against 6 codebase files + governing spec
**Risk Level:** 🟢 Low

Reviewed the plan against its reference chain: ROADMAP line 8.2.1 → `.ai-factory/specs/49-localization-contract.md` (governing spec) → the targeted code (`src/llm/client.py`, `src/reasoning/reasoner.py`, `src/episodic/linked_change.py`, `tests/reasoning/conftest.py`, `tests/reasoning/test_narrate.py`).

### Context Gates
- **Architecture (`.ai-factory/ARCHITECTURE.md`):** OK. New files land in the existing `src/reasoning/` feature package. `localizer.py` importing `Reasoner`/`Translator` (same feature) and `LinkedChange` (episodic's public value object) mirrors the already-established dependency direction in `reasoner.py`, which imports `LinkedChange` from `src/episodic/`. No boundary violation.
- **Rules (`.ai-factory/RULES.md`):** OK. File is intentionally empty (no project counter-defaults); nothing to enforce.
- **Roadmap (`.ai-factory/ROADMAP.md`):** Aligned. Plan title `8.2.1 — Localization contract (red tests)` matches the roadmap contract line and its `Spec:` tag resolves to `specs/49-localization-contract.md`. Every dispatch invariant in the plan (one `narrate(pivot)` + per-lang `translate` with `source_lang=pivot`; `NativeLocalizer` → `len(langs)` narrations; empty-`langs` → empty dict, zero calls; keys == `langs` exactly; stubs raise / tests red) traces directly to the spec's Change and Guards sections.

### Verified Assumptions (all correct)
- **ABC style match:** `src/llm/client.py` uses `from abc import ABC, abstractmethod` with `async def ... -> str: ...` — exactly the style Task 1 instructs to follow. Project ABCs (`LLMClient`, `EpisodicStore`, `KnowledgeStore`, `ProjectGraph`) use plain marker-less names, so `Translator`/`Localizer` are consistent with the pinned project convention.
- **`narrate` signature:** `Reasoner.narrate(self, change: LinkedChange, lang: str = "ru") -> str` exists; both localizers' positional `narrate(change, lang)` calls match it.
- **`LinkedChange` import path:** `src/episodic/linked_change.py` defines `LinkedChange` (frozen dataclass) — the import in Task 2 is correct.
- **`Reasoner` import path:** `src/reasoning/reasoner.py` defines `Reasoner` (concrete class, not an ABC) — Task 2's constructor typing is correct, and Task 3's guidance to make `FakeNarratingReasoner` a minimal duck-typed stand-in (rather than subclass the concrete `Reasoner`) is the right call.
- **conftest fake style:** `FakeLLMClient`/`FakeEmbedder` recording-fake pattern (`calls` list + deterministic per-call marker) exists in `tests/reasoning/conftest.py` — Task 3's `FakeNarratingReasoner`/`FakeTranslator` mirror it faithfully, and `FakeTranslator(Translator)` subclassing the new ABC matches how existing fakes subclass their ABCs.
- **`_make_change` pattern:** present in `tests/reasoning/test_narrate.py` as a module-local helper; Task 3's "reuse the pattern or add a shared helper" correctly accounts for the fact that it is not currently in conftest.
- **Async test execution:** `pyproject.toml` sets `asyncio_mode = "auto"` with `pytest-asyncio` in dev deps, so bare `async def test_...` functions run — the red tests will execute and fail at the awaited `notes(...)` call (uncaught `NotImplementedError`), which is the intended red state per the spec's Verification section.
- **No collisions:** `src/reasoning/translator.py` and `src/reasoning/localizer.py` do not yet exist; `tests/reasoning/test_localizer.py` does not yet exist. All packages already carry `__init__.py`.

### Critical Issues
None.

### Positive Notes
- The plan correctly keeps the pivot's `source_lang` wiring honest: Task 4 explicitly forbids relying on `translate`'s `"en"` default and prescribes a non-`"en"` (`pivot="ru"`) assertion path — directly guarding the spec's "a non-`en` pivot is not silently read as `en`" silent-failure surface.
- Empty-`langs` zero-call invariant and the exact-key-set assertion for both strategies are pinned in Task 5, covering the "Pivot must not narrate the pivot when nothing is requested" and "pivot generated-but-not-returned" cases from the spec.
- Task ordering and dependencies (`Task 2 → 1`, `3 → 2`, `4/5 → 3`) are coherent, and the split cleanly leaves real translation quality to 8.2.2's eval harness, matching the spec guard that call-count assertions run against mocks only.
- Docstrings-as-dispatch-contract for the raising stubs is a good move: it hands 8.2.2 the intended dispatch without letting 8.2.1 redesign it.

PLAN_REVIEW_PASS
