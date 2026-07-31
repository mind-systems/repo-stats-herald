## Plan Review — 21.3 Report eval cases with no reference

**Plan:** `.ai-factory/plans/14-21-3-report-eval-cases-with-no-reference.md`
**Spec:** `.ai-factory/specs/64-missing-reference-report.md`
**Files reviewed:** `scripts/eval.py`, `CLAUDE.md`, `tests/` layout, `pyproject.toml`
**Risk Level:** 🟡 Medium

### Context Gates
- **Roadmap** (`.ai-factory/ROADMAP.md`, line 46 — task 21.3): the plan matches the contract line exactly — presence-check per case after the per-case writes, one closing summary, non-fatal, exit status unchanged, presence checking only (no diffing/scoring), and a `CLAUDE.md` doc update. Aligned.
- **Spec** (`64-missing-reference-report.md`): every clause is covered — symmetric reference-directory derivation, the "same shape as the top-of-method `unregistered` check but non-fatal" framing, the four verification criteria, and the "first test module" note. Aligned.
- **Architecture / Rules**: no `.ai-factory/ARCHITECTURE.md` boundary is crossed — all work stays inside the `scripts/` composition-root entrypoint and its test; no feature-to-feature dependency introduced. `CLAUDE.md` logging rule ("never log with `print`") is respected: the plan's Settings note correctly scopes this as harness `print` output mirroring the existing `wrote <path>` line, not a `logging` concern. No migration involved (no schema touched).

### Critical Issues

**1. Task 4: the test's output and reference directories must be *distinct*, or every arrangement collapses.**
`EvalRunner.run` writes each output to `self._out_dir / f"{case.name}.md"` (loop, current lines 173–177) and *then* computes `missing` from `self._reference_dir / f"{case.name}.md"` (Task 3). If both are pointed at the same directory — which is exactly what Task 4's literal instruction says: `construct EvalRunner({...}, out_dir=<tmp>, reference_dir=<tmp>) using pytest's tmp_path` (a single `tmp_path` fixture is one directory) — then the outputs the run just wrote *are* the reference files the check then finds. `missing` is always empty, and the "no case has a reference" and "some cases have references, some do not" arrangements become impossible to express.

The spec's verification is explicit that "each of the four criteria below is arranged by which temp files exist before the call" — this only works if `reference_dir` is a separate directory that the run never writes into. Task 4 must instruct the implementer to use two distinct directories (e.g. `out_dir = tmp_path / "out"` and `reference_dir = tmp_path / "reference"`, or `tmp_path_factory`), and to populate only `reference_dir` when arranging each case. As written, an implementer following the literal `out_dir=<tmp>, reference_dir=<tmp>` will produce tests that cannot distinguish the arrangements the task exists to verify.

### Positive Notes
- **Task 1 anchor is exact.** `_OUT_DIR = _EVALS_DIR / "out"` is indeed at line 46; adding `_REFERENCE_DIR = _EVALS_DIR / "reference"` immediately after keeps the two derivations symmetric, and the module-level constant is defined before `EvalRunner`, so it is valid as a default-argument value.
- **Task 2 preserves existing wiring.** Widening `__init__` with defaulted `out_dir`/`reference_dir` keeps `EvalRunner(handlers)` at line 238 working unchanged, and swapping the three module-level `_OUT_DIR` uses inside `run` for `self._out_dir` is behaviorally identical. (Minor: the plan quotes the signature as `def __init__(self, handlers)` while the code is `def __init__(self, handlers: dict[str, CaseHandler]) -> None` — a harmless paraphrase, not a defect.)
- **Task 3 mirrors the existing `unregistered` idiom faithfully** (enumerate → collect failures → report once) and honors every guard: no raise, return value and exit status untouched, `wrote {out_path}` untouched, presence-only via `Path.exists()`.
- **`__init__.py` marker is correctly required.** Sibling packages (`tests/commits/__init__.py`, etc.) all carry one, so `tests/scripts/__init__.py` matches convention.
- **Async test approach is sound.** `pyproject.toml` sets `asyncio_mode = "auto"` (pytest-asyncio), so a plain `async def test_...` is auto-collected; `asyncio.run` is equally valid. Both options the plan lists work.
- **Task 5 doc update** is scoped to the eval-harness section, present-tense, behavior-not-code, with no plan/`.ai-factory` reference — consistent with the documentation rules.

## Deferred observations
_None._

One blocking correctness gap in the test design (Critical Issue 1) must be resolved in Task 4 before implementation. Fix that and the plan is complete and faithful to the spec.
