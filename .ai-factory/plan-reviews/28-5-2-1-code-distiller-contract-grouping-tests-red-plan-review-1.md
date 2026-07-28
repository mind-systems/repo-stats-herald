## Code Review Summary

**Artifact Reviewed:** `.ai-factory/plans/28-5-2-1-code-distiller-contract-grouping-tests-red.md`
**Files it targets:** `src/knowledge/code_distiller.py` (new), `tests/knowledge/test_code_distiller_contract.py` (new)
**Risk Level:** 🟢 Low

### Context Gates

- **Architecture (`.ai-factory/ARCHITECTURE.md`):** PASS. `CodeDistiller` lands in the `knowledge/` feature package, receives its `LLMClient` by constructor injection, and constructs no concrete client — matching "Abstractions at every external seam", "Dependency injection via constructor", and "Concrete implementations chosen only at the composition root". The `distill/group_units/compose` split keeps prompt/composition details inside the owning class (Key Principle 6). No feature-to-feature reach: the module depends only on `src/llm/client.py` (infra).
- **Rules (`.ai-factory/RULES.md`):** PASS. File is intentionally empty (no counter-defaults); nothing to enforce.
- **Roadmap (`.ai-factory/ROADMAP.md` line 60, task 5.2.1):** PASS. The plan realizes the contract line's demand — "N paths across M modules → M bounded prompts (never one unbounded), every selected path covered by exactly one unit, per-unit results composed into one text", red over a mocked `LLMClient`, LLM quality deferred to 5.2.2.
- **Governing spec (`.ai-factory/specs/46-code-distiller-contract.md`):** PASS. The plan honors every clause: stubbed `distill` raising `NotImplementedError`; pure grouping/composition seam directly testable and not redesigned by 5.2.2; bounded units asserted mechanically by count; LLM-output quality excluded. The plan's decision to stub `group_units`/`compose` as raising in the red state is consistent with the spec's Verification ("red only where the logic doesn't exist yet — stub raises") and its Guard ("the grouping/composition helpers are pure and directly testable ... 5.2.2 wires them to real prompting, it does not redesign them").
- **Skill-context (`.ai-factory/skill-context/aif-review/SKILL.md`):** absent — no project overrides to apply.

### Critical Issues

None.

### Verification against ground truth

- **`LLMClient` seam (`src/llm/client.py`):** confirmed — `LLMClient(ABC)` with a single `async def generate(self, prompt: str) -> str`. The plan's import path `from src.llm.client import LLMClient` and the `FakeLLMClient(LLMClient)` override of `generate` are correct and instantiable (the sole abstract method is overridden).
- **Concrete-class idiom:** confirmed against `LinkedChangeResolver` (`src/episodic/linked_change.py`) and `Summarizer` (`src/summarization/service.py`) — both are concrete classes taking abstractions by constructor. `CodeDistiller` as a concrete class (not an ABC) is the right call; the global "interface names declare their kind" rule does not apply, since `CodeDistiller`/`CodeUnit` are a concrete service and a value object, not abstractions.
- **Red-test idiom:** confirmed — `tests/episodic/test_linked_change_contract.py`, `tests/github/test_app_auth_single_flight.py`, and `tests/github/test_mirror_isolation.py` all use the "fails only because the method raises `NotImplementedError`, never on import/fixture/collection" module-docstring pattern the plan mirrors.
- **Test placement / conftest laziness:** confirmed — `tests/knowledge/conftest.py` imports `asyncpg`/`create_pool`/`PgVectorStore` at module scope (these resolve cleanly, since sibling tests collect today) but opens a DB connection only inside the `pg_pool` fixture. New tests that request neither `pg_pool` nor `store` touch no database, so the plan's "lazy and unused here" claim holds and the suite collects without a live pgvector.
- **Module key `os.path.dirname(path)`:** a sound, mechanical reading of the spec's "per package/module" — root files → `""` (one root module), same-parent paths → one `CodeUnit`. The plan correctly flags that intra-package size-bounding is not required by the spec and is deferred.
- **Target files:** confirmed absent today — appropriate starting state for a red task.

### Positive Notes

- The "M bounded prompts ⇄ M units" equivalence is explicitly reasoned: since 5.2.2 issues one prompt per `CodeUnit` and `distill` is stubbed here, pinning the unit count (plus full/disjoint coverage) genuinely pins the bounded-prompt invariant without needing mirror/file machinery in the red task. This resolves what could otherwise look like a coverage gap between the spec's "M prompts" and the plan's "M units".
- Determinism is pinned end-to-end (sorted module key, sorted paths within a unit, ordered `"\n\n"` join), so the composition test's byte-identical assertion is well-founded.
- The `FakeLLMClient.calls`-stays-empty test cleanly encodes the "no model call leaks into the deterministic seam" guard as a standing regression check for 5.2.2.
- Scope discipline is exact: LLM-output quality is repeatedly and correctly pushed to the eval harness / 5.2.2, matching both spec and roadmap.

## Deferred observations

- Affects: 5.2.2 (`.ai-factory/specs/33-code-to-feature-distillation.md`) — `compose` is pinned to join per-unit strings with a bare `"\n\n"` separator. That is fully adequate for the determinism this red task asserts, but when 5.2.2 turns the seam green it produces the actual feature-level document fed to the store; if that document benefits from per-unit headings or delimiters, the format lives in `compose` and can be enriched there without disturbing these tests (they assert order + separator presence + determinism, not the absence of additional structure). Nothing to change now — flagged so the format choice is a conscious one when the real composition lands. [dismissed]

PLAN_REVIEW_PASS
