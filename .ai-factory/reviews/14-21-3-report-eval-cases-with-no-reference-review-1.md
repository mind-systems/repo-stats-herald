# Code Review — 21.3 Report eval cases with no reference

**Plan:** `.ai-factory/plans/14-21-3-report-eval-cases-with-no-reference.md`
**Files reviewed (in full):** `scripts/eval.py`, `tests/scripts/test_eval.py`, `tests/scripts/__init__.py`, `CLAUDE.md` (diff)
**Verdict:** Pass — no findings.

## What was checked

**Task 1 — `_REFERENCE_DIR` constant.** `_REFERENCE_DIR = _EVALS_DIR / "reference"` is added directly after `_OUT_DIR` (eval.py:47), symmetric with the output path and pointing at the real `evals/reference/` directory (confirmed to exist with the six authored notes). Defined before `EvalRunner`, so valid as a default-argument value. `_CASES_FILE`/`_OUT_DIR` untouched.

**Task 2 — `EvalRunner` constructor widening.** `__init__` now takes defaulted `out_dir`/`reference_dir` (eval.py:162–170); the three former module-level `_OUT_DIR` uses inside `run` map one-for-one to `self._out_dir` (mkdir, `out_path`, `wrote` line). Defaults preserve the production wiring — `_run()` still calls `EvalRunner(handlers)` unchanged (eval.py:238), so `make eval` behaves identically.

**Task 3 — missing-reference summary.** The `missing` comprehension mirrors the top-of-method `unregistered` idiom (enumerate → collect failures → report once) and honors every guard:
- Non-fatal: no `raise`, `run` still returns `None`, exit status unchanged.
- Presence-only via `Path.exists()` — no reading, diffing, or scoring of reference content.
- The per-case `wrote {out_path}` line is untouched; the summary is additive and printed once after the loop.
- Correctly does *not* mkdir `reference_dir` — a missing dir yields `exists() == False`, the intended signal. The f-string concatenation (`"...no reference " + "to compare against: ..."`) joins with a correct single space.

**Task 4 — test module.** Uses two distinct directories (`tmp_path / "out"`, `tmp_path / "reference"`), the round-1 blocking concern. Reference files are arranged before the call, `out_dir` is never confused with `reference_dir`, and each of the four spec criteria is covered (all-missing, partial, none-missing, and `result is None` asserted in every case). Stub handler needs no model/pool/tunnel. Ran the module: **3 passed**. `tests/scripts/__init__.py` is an empty marker matching sibling packages; `pyproject.toml` confirms `asyncio_mode = "auto"` and `pythonpath = ["."]`, so the plain `async def` tests are auto-collected and `from scripts.eval import ...` resolves.

**Task 5 — docs.** The eval-harness section of `CLAUDE.md` gains a present-tense description of the closing summary, explicitly framed as presence reporting that never fails the run or changes exit status. Behavior-not-code, no plan/`.ai-factory` reference.

## Runtime risk assessment

No schema/migration touched, no new dependency, no I/O beyond an existing directory pattern, no concurrency change. The one behavioral addition (a `print` after the write loop) cannot raise on the presence check (`Path.exists()` swallows a missing dir) and cannot affect the process exit status. Nothing observed that breaks at runtime.

REVIEW_PASS
