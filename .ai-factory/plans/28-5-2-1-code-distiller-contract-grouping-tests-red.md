# Plan: 5.2.1 — Code distiller contract + grouping tests (red)

## Context
Pin `CodeDistiller`'s signature and its bounded-unit grouping/composition mechanics — the deterministic, mockable half of the code-to-feature distiller — with red tests, before the real LLM-prompting lands in 5.2.2. The load-bearing invariant "bounded units — per package/module, never the whole codebase in one prompt" moves from prose into a mechanical assertion. LLM-output quality stays out of scope (eval harness, 5.2.2).

## Settings
- Testing: yes (this task *is* the red test suite)
- Logging: none
- Docs: no

## Design decisions (pin these for 5.2.2)

Follow the existing concrete-class idiom (`Summarizer`, `LinkedChangeResolver`): `CodeDistiller` is a concrete class, not an ABC — the model-agnostic swap seam is the injected `LLMClient` (per ARCHITECTURE.md "abstractions at every external seam"; the LLM boundary is already that seam). It is constructed at a composition root and never builds its own client.

The three public methods form the stable interface 5.2.2 fills in (5.2.2 wires them to real prompting, it does **not** redesign them):

- `group_units(paths)` and `compose(unit_texts)` are the **pure** grouping/composition seam — no LLM call, directly testable. In this red task their bodies raise `NotImplementedError`, so the tests are red exactly as `LinkedChangeResolver.resolve`'s red tests are (they call the method as if implemented; it raises; 5.2.2 turns them green unchanged).
- `distill(repo, paths)` is the LLM-facing orchestration (group → per-unit prompt/read → compose); stubbed to raise here.

**Module/unit key (pinned):** a path's module is its parent directory — the substring up to and including the last `/` removed, i.e. `os.path.dirname(path)` (a repo-root file → `""`, the root module). Paths sharing a parent directory form exactly one `CodeUnit`. This is the concrete reading of "per package/module" and is what makes "M distinct modules → M units, never one giant unbounded unit" a mechanical count. Further size-bounding *within* a single package is not required by the spec and is deferred.

**Stable order (pinned):** `group_units` returns units sorted by module key (ascending); paths within a unit sorted ascending. `compose` concatenates its input strings in the given order, joined by a blank line (`"\n\n"`). Because the units arrive from `group_units` in sorted order, the composed text is deterministic across runs — which is what the composition test asserts.

**"M bounded prompts" ⇄ "M units":** 5.2.2 issues exactly one LLM prompt per `CodeUnit`, so pinning the unit count and full/disjoint path coverage here *is* pinning the bounded-prompt invariant; no file/mirror machinery is needed in this red task. The mocked `LLMClient` is injected at construction and asserted untouched by the pure grouping/composition path — proving no real (or mocked) model call leaks into the deterministic seam.

## Tasks

### Phase 1: Contract & stub

- [x] **Task 1: `CodeDistiller` contract + `CodeUnit` value object (stub)**
  Files: `src/knowledge/code_distiller.py`
  Add a new module in the `knowledge` feature package.
  - `@dataclass(frozen=True) class CodeUnit:` with `module: str` and `paths: tuple[str, ...]` — a single bounded grouping of selected paths sharing one module key.
  - `class CodeDistiller:` constructed as `def __init__(self, llm: LLMClient) -> None:` (import `LLMClient` from `src.llm.client`); store it as `self._llm`. Do not construct any concrete client — the composition root injects one.
  - `async def distill(self, repo: str, paths: list[str]) -> str:` — stub: `raise NotImplementedError`. Docstring states the eventual flow (group → one bounded prompt per unit read from the mirror → compose) and that per-unit LLM-output quality is 5.2.2's concern.
  - `def group_units(self, paths: list[str]) -> list[CodeUnit]:` — stub: `raise NotImplementedError`. Docstring pins the parent-directory module key, the bounded-unit invariant ("never the whole codebase as one unit"), full/disjoint coverage of the input, and the sorted (module, then path) order.
  - `def compose(self, unit_texts: list[str]) -> str:` — stub: `raise NotImplementedError`. Docstring pins: concatenate the per-unit description strings in the given order, joined by `"\n\n"`, deterministically.
  - Type hints throughout; describe behavior in docstrings, not implementation notes, and cite no plan/roadmap references in comments.

### Phase 2: Red tests

- [x] **Task 2: Grouping & composition red tests over a mocked `LLMClient`** (depends on Task 1)
  Files: `tests/knowledge/test_code_distiller_contract.py`
  New test module in `tests/knowledge/` (no DB — the pgvector fixtures in `tests/knowledge/conftest.py` are lazy and unused here). Mirror the style of `tests/episodic/test_linked_change_contract.py`: a module docstring stating every test calls the method as if implemented and fails only because the stub raises `NotImplementedError` (never on import/fixture/collection), and 5.2.2 greens them unchanged.
  - Define a local `class FakeLLMClient(LLMClient):` whose `async def generate(self, prompt)` appends `prompt` to a recording list and returns a deterministic per-call marker string (e.g. `f"desc:{len(self.calls)}"`). It is the injected boundary and the proof that the pure seam touches no model.
  - Build `CodeDistiller(FakeLLMClient())` in each test (or a small local fixture/factory).
  - **Test — unit count matches module count (bounded, never one giant unit):** a `paths` list of N files spanning M distinct parent directories → `group_units(paths)` returns `len == M`; assert every returned `CodeUnit.paths` shares one parent directory (no unit spans >1 module), and that no single unit contains all N paths.
  - **Test — full, disjoint coverage:** the union of every unit's `paths` equals the input set and the total path count across units equals N — no path dropped, none duplicated across units. Include ≥2 paths in the same directory to prove they collapse into one unit rather than fragmenting.
  - **Test — stable-order composition:** `compose(["unit-a", "unit-b", "unit-c"])` returns a single string containing each input in the given order, joined by the pinned separator; calling it twice with the same input yields byte-identical output (determinism).
  - **Test — grouping order is stable/sorted:** `group_units` over a deliberately unsorted `paths` list returns units in ascending module-key order (so the downstream compose order is deterministic regardless of input order).
  - **Test — pure seam issues no model call:** after `group_units`/`compose` are exercised (in green, 5.2.2), the injected `FakeLLMClient.calls` stays empty — asserting the deterministic seam never awaits `generate`. (Red now via the stub; documents the "never a real model call" guard.)
  - Confirm the suite is red purely on `NotImplementedError`: `uv run pytest tests/knowledge/test_code_distiller_contract.py` collects cleanly and every failure is the stub raising — not an `ImportError`, missing fixture, or signature mismatch.
