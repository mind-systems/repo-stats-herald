# Code Review: 8.2.1 — Localization contract (red tests)

**Scope reviewed:** `src/reasoning/translator.py`, `src/reasoning/localizer.py`, `tests/reasoning/conftest.py` (additions), `tests/reasoning/test_localizer.py` — read in full against the governing spec (`.ai-factory/specs/49-localization-contract.md`), the plan, and the surrounding code (`src/reasoning/reasoner.py`, `src/episodic/linked_change.py`, `src/commits/models.py`, `src/llm/client.py`).

**Nature of the task:** This is a red-tests contract task. The deliverable is two ABCs, raising stubs, and tests that fail *now* (against the stubs) and are greened by 8.2.2. So a stub raising `NotImplementedError` is the intended state, not a defect.

## Verification performed

- **Tests are red for the right reason.** `uv run pytest tests/reasoning/test_localizer.py` → 8 failed, all with `NotImplementedError` raised from `localizer.py:56`/the pivot stub — i.e. they reach and await `notes(...)` and fail there, not at import/collection or on a malformed assertion. This is the correct red state per the spec's Verification section.
- **No collateral breakage.** `uv run pytest tests/reasoning/` → 8 failed (the new red tests), 18 passed (all pre-existing reasoning tests). The conftest additions (`FakeNarratingReasoner`, `FakeTranslator`, `make_change` fixture, two fixtures) do not disturb existing fixtures or tests.
- **Signatures/imports check out.** `Reasoner.narrate(change, lang="ru")` matches the localizers' positional `narrate(change, lang)` calls; `Commit`/`CommitContext` fields match the `make_change` fixture; `LinkedChange`, `Reasoner`, `Translator` import paths resolve; no circular import (`reasoner.py` does not import `localizer.py`). `asyncio_mode = "auto"` is set, so the bare `async def test_*` functions execute.

## Correctness of the pinned invariants

Each spec silent-failure surface is pinned by a test that a *wrong* implementation could not pass:

- **Pivot narrates once, not per-language** — `fake_narrating_reasoner.calls == [(change, "en")]` (exactly one call regardless of lang count).
- **Pivot never self-translates its own pivot** — `result["en"] == "narrated:en"` (raw narrate output) and `fake_translator.calls == [("narrated:en", "ru", "en")]` (only the non-pivot lang translated).
- **`source_lang=pivot` honored, not the `"en"` default** — the dedicated `pivot="ru"` test asserts `translate(..., source_lang="ru")`, so a non-`en` pivot silently read as `en` would fail.
- **Pivot generated-but-not-returned when unrequested** — `{"ru","de"}` case asserts one `narrate("en")`, two translates, and `"en" not in result`.
- **Native calls `narrate` exactly `len(langs)` times, one per lang** — set of recorded langs equals `langs`; `fake_translator.calls == []`.
- **Empty `langs` → empty dict, zero calls** for both strategies (Pivot does not speculatively narrate the pivot).
- **Result keys == `langs` exactly** for both strategies.

Order-sensitivity is handled correctly (the multi-translate case uses `sorted(...)`, and lang-set assertions use `set(...)`), so a valid implementation with nondeterministic set iteration order won't be falsely rejected. The docstrings on `PivotLocalizer`/`NativeLocalizer` accurately encode the intended dispatch for 8.2.2 without citing the plan layer.

## Findings

No correctness, security, or bug findings.

Non-blocking observation (not a defect, no action required): `tests/reasoning/test_narrate.py` retains its own module-local `_make_change`, so the new shared `make_change` conftest fixture leaves two near-identical builders in the package. The plan explicitly permitted either reuse or a shared helper, so this is within scope; a future cleanup could migrate `test_narrate.py` onto the fixture.

REVIEW_PASS
