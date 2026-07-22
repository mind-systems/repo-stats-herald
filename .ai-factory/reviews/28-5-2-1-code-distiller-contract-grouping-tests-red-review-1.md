# Code Review: 5.2.1 — Code distiller contract + grouping tests (red)

**Reviewed:** `git diff HEAD` on branch `dev`
**Code files changed:** `src/knowledge/code_distiller.py` (new), `tests/knowledge/test_code_distiller_contract.py` (new)
**Verdict:** No correctness, security, or runtime defects found.

## Scope

This is a red-test task: the production code is pure stubs raising `NotImplementedError`, and the deliverable is a test suite that (a) fails today only because the stubs raise, and (b) turns green **unchanged** once 5.2.2 implements the pinned grouping/composition mechanics. The review therefore checks two things a normal diff review would not: that the red state is clean (no import/fixture/collection failures masquerading as red), and that the assertions are green-able by a spec-conformant implementation while still catching the invariant they exist to protect.

## Runtime / red-state verification (executed)

`uv run pytest tests/knowledge/test_code_distiller_contract.py -q` → **5 failed**, every failure a bare `NotImplementedError` raised from `code_distiller.py` (`group_units` at line 53, `compose` for the composition test). No `ImportError`, no missing fixture, no signature mismatch, no collection error. The module imports cleanly (`CodeDistiller`, `CodeUnit`, `LLMClient` all resolve), `FakeLLMClient(LLMClient)` is instantiable (it overrides the sole abstract `generate`), and the `fake_llm`/`distiller` fixtures wire without touching the pgvector fixtures in `tests/knowledge/conftest.py` (those open a DB connection only inside `pg_pool`, which no test here requests). This matches the plan's Verification clause exactly.

## Green-ability verification (traced against a spec-conformant impl)

Modeling the natural implementation the plan pins — `group_units` = group by `os.path.dirname(path)`, units sorted by module key, paths sorted within a unit; `compose` = `"\n\n".join(unit_texts)` — every assertion holds:

- **`test_unit_count_matches_module_count`** — 4 paths over modules `src/a` (2 files), `src/b`, `src/c` → 3 units; each unit's paths share one parent; each unit strictly smaller than the full set. Green.
- **`test_grouping_is_full_and_disjoint`** — includes a repo-root file (`readme.md` → module `""`), exercising the root-module edge; union equals input, no drop, no duplicate. Green.
- **`test_composition_is_stable_and_ordered`** — pins the `"\n\n"` separator and byte-identical determinism. Green.
- **`test_grouping_order_is_sorted_by_module`** — unsorted input yields `["src/a", "src/b", "src/c"]` and sorted paths within each unit. Green.
- **`test_pure_seam_issues_no_model_call`** — `group_units`/`compose` never await `generate`, so `FakeLLMClient.calls` stays empty. Green.

The test's inner parent-directory recomputation (`path.rsplit("/", 1)[0] if "/" in path else ""`) is value-equivalent to the implementation's `os.path.dirname` for the POSIX-style, no-trailing-slash paths used, so the two never disagree.

## Invariant-coverage check (does the red suite catch the bug it targets?)

The load-bearing invariant is "never one giant unbounded unit." Traced against buggy implementations:
- One unit holding all paths → `test_unit_count_matches_module_count` (`len(units) == 3`) fails. Caught.
- A dropped path → `test_grouping_is_full_and_disjoint` (`sorted(covered) == sorted(paths)`) fails. Caught.
- A path duplicated across units → same test's length/set assertions fail. Caught.
- Unsorted output → `test_grouping_order_is_sorted_by_module` fails. Caught.

The suite mechanically pins the bounded-unit invariant rather than asserting only "it ran," as the spec Guard requires.

## Architecture / convention conformance

- `CodeDistiller` receives its `LLMClient` by constructor injection and constructs no concrete client — matches the composition-root discipline and the concrete-class idiom of `Summarizer`/`LinkedChangeResolver`.
- `code_distiller.py` depends only on infra (`src/llm/client.py`), no cross-feature import.
- Docstrings describe behavior and pin the contract (module key, ordering, separator); no plan/roadmap references leak into comments. Type hints present throughout.
- Test module mirrors the established red-test docstring pattern (`tests/episodic/test_linked_change_contract.py`).

## Security

No external input, file I/O, network, or DB access is introduced. Nothing to assess beyond the above.

REVIEW_PASS
