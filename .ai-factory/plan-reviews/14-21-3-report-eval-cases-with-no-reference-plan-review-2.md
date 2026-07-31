## Plan Review — 21.3 Report eval cases with no reference (round 2)

**Plan:** `.ai-factory/plans/14-21-3-report-eval-cases-with-no-reference.md`
**Spec:** `.ai-factory/specs/64-missing-reference-report.md`
**Files reviewed:** `scripts/eval.py`, `CLAUDE.md`, `tests/` layout, `pyproject.toml`, roadmap line 46
**Risk Level:** 🟢 Low

### Context Gates
- **Roadmap** (`.ai-factory/ROADMAP.md`, line 46 — task 21.3): the plan matches the contract line exactly — presence-check per case after the per-case writes, one closing summary naming every case without a reference and stating how many of how many, non-fatal, exit status unchanged, presence checking only (no diffing/scoring), plus the `CLAUDE.md` doc update. Aligned.
- **Spec** (`64-missing-reference-report.md`): every clause is covered — symmetric reference-directory derivation, the "same shape as the top-of-method `unregistered` check but non-fatal" framing, the four verification criteria, and the "harness's first test module" note. Aligned.
- **Architecture / Rules**: no `.ai-factory/ARCHITECTURE.md` boundary is crossed — all work stays inside the `scripts/` composition-root entrypoint and its new test; no feature-to-feature dependency introduced, no schema/migration touched. The `CLAUDE.md` "never log with `print`" rule is respected: the plan's Settings note correctly scopes this as harness `print` output mirroring the existing `wrote <path>` line, an established pattern in `scripts/eval.py`, not a `logging` concern.

### Resolution of the round-1 blocking issue
Round 1's sole Critical Issue — the test's output and reference directories collapsing into one `tmp_path` and making every arrangement produce an empty `missing` — is fully resolved. Task 4 now mandates **two distinct directories** (`out_dir = tmp_path / "out"`, `reference_dir = tmp_path / "reference"`), spells out *why* a shared directory would make the outputs the run just wrote become the presence-check's own hits, and instructs arranging each case by creating (or not) `reference_dir / f"{case.name}.md"` *before* the call while keeping `reference_dir` a directory the run never writes into. The gap that blocked round 1 is closed.

### Verification against ground truth
- **Task 1 anchor is exact.** `_OUT_DIR = _EVALS_DIR / "out"` is at line 46; inserting `_REFERENCE_DIR = _EVALS_DIR / "reference"` immediately after keeps the derivations symmetric, and the constant is defined before `EvalRunner`, so it is valid as a default-argument value. `evals/reference/` is the correct directory (spec and roadmap both confirm the six reference notes live there).
- **Task 2 preserves wiring.** Confirmed live signature is `def __init__(self, handlers: dict[str, CaseHandler]) -> None`; the plan's `def __init__(self, handlers)` is a harmless paraphrase. Defaulting `out_dir`/`reference_dir` keeps `EvalRunner(handlers)` at line 238 working unchanged, and the three module-level `_OUT_DIR` uses inside `run` (mkdir, `out_path`, `wrote` line) map one-for-one to `self._out_dir`.
- **Task 3 mirrors the `unregistered` idiom** (enumerate → collect failures → report once) and honors every guard: no raise, return value and exit status untouched, `wrote {out_path}` untouched, presence-only via `Path.exists()`. Correctly does **not** mkdir `reference_dir` — a missing reference dir yields `exists() == False`, which is the intended non-fatal signal.
- **Test package + async config verified.** Sibling `tests/<pkg>/__init__.py` files are empty markers, so `tests/scripts/__init__.py` matches convention. `pyproject.toml` sets `asyncio_mode = "auto"` and `pythonpath = ["."]`; I confirmed `from scripts.eval import EvalRunner, Case, CaseHandler` imports cleanly even though `scripts/` has no `__init__.py` (implicit namespace package), so the test module's import path is sound. Both `asyncio.run` and a plain `async def test_...` the plan offers are auto-collected.
- **Task 5 doc update** is scoped to the eval-harness section, present-tense, behavior-not-code, no plan/`.ai-factory` reference — consistent with the documentation rules.

### Positive Notes
- The revised Task 4 doesn't just state the fix — it embeds the failure-mode reasoning inline, so an implementer cannot regress to a single shared directory without contradicting the task text.
- The four verification criteria map exactly onto the spec's four bullets, including the "exit status identical across all three" invariant, expressed concretely as "`run` returns `None`, never raises, in every arrangement."

## Deferred observations
_None._

The one blocking gap from round 1 is resolved and every task anchor, signature, path, and config assumption is confirmed against the current code. The plan is complete and faithful to the spec.

PLAN_REVIEW_PASS
