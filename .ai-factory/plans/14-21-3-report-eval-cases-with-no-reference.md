# Plan: 21.3 — Report eval cases with no reference

## Context
Make a measure-nothing eval run visible: after `EvalRunner.run` writes each case's output, check for the matching `evals/reference/<case>.md` and print one closing summary naming every case with no reference and stating how many of how many cases had nothing to compare against. Presence checking only — non-fatal, no diffing or scoring, exit status unchanged.

## Settings
- Testing: yes (task explicitly adds `tests/scripts/test_eval.py`, the harness's first test module)
- Logging: minimal (the harness reports via `print`, mirroring the existing `wrote <path>` line — no `logging` change)
- Docs: yes (task explicitly updates the eval-harness section of `CLAUDE.md`)

## Tasks

### Phase 1: Reference report in the runner

- [x] **Task 1: Derive the reference directory symmetrically with the output directory**
  Files: `scripts/eval.py`
  Add a module-level `_REFERENCE_DIR = _EVALS_DIR / "reference"` immediately after the existing `_OUT_DIR = _EVALS_DIR / "out"` (around line 46), so a case's reference path derives from `_REFERENCE_DIR` exactly as its output path derives from `_OUT_DIR` (`<dir> / f"{case.name}.md"`). Do not touch `_CASES_FILE`/`_OUT_DIR` values.

- [x] **Task 2: Let `EvalRunner` take output and reference directories so the run is drivable against temp paths** (depends on Task 1)
  Files: `scripts/eval.py`
  Widen `EvalRunner.__init__` (currently `def __init__(self, handlers)`) to also accept `out_dir: Path = _OUT_DIR` and `reference_dir: Path = _REFERENCE_DIR`, storing them as `self._out_dir` / `self._reference_dir`. Update `run` to use `self._out_dir` in place of the module-level `_OUT_DIR` (the `mkdir`, the per-case `out_path`, and the `wrote {out_path}` line stay behaviorally identical). Defaults preserve today's `main()` wiring; the test overrides them. `_run()` continues constructing `EvalRunner(handlers)` unchanged.

- [x] **Task 3: Print the missing-reference summary once after the per-case writes** (depends on Task 2)
  Files: `scripts/eval.py`
  After the existing per-case write loop in `EvalRunner.run`, following the same shape as the `unregistered` check at the top of the method (enumerate cases, collect the ones failing the condition, report once), collect `missing = [case.name for case in cases if not (self._reference_dir / f"{case.name}.md").exists()]`. Then print a single closing summary:
  - When `missing` is non-empty: name every missing case in one message and state the count plainly — how many of how many cases had no reference to compare against (e.g. `2 of 6 eval cases have no reference to compare against: <name>, <name>`).
  - When `missing` is empty: state plainly that every case has a reference (e.g. `all 6 eval cases have a reference`).
  Guards to honor exactly: non-fatal — do not raise, do not alter the return value or exit status; every output is still written; the existing `wrote {out_path}` line is untouched; presence checking only via `Path.exists()` — no reading, diffing, or scoring of reference content.

### Phase 2: Test and docs

- [x] **Task 4: Add the harness's first test module driving `EvalRunner.run` against temp dirs** (depends on Task 3)
  Files: `tests/scripts/__init__.py`, `tests/scripts/test_eval.py`
  Create the empty `tests/scripts/__init__.py` package marker (matching every other `tests/<pkg>/__init__.py`). In `test_eval.py`, define a minimal stub `CaseHandler` subclass whose async `run` returns a fixed string (no live model, no pool, no SSH tunnel), build `Case` objects directly, and construct `EvalRunner`.
  **The output and reference directories must be two distinct directories** — e.g. `out_dir = tmp_path / "out"` and `reference_dir = tmp_path / "reference"` (both under `tmp_path`, but separate paths). A single shared directory would collapse every arrangement: the run writes each output to `out_dir / f"{case.name}.md"` and then computes `missing` from `reference_dir / f"{case.name}.md"`, so if the two dirs are the same, the outputs the run just wrote become the very files the presence check finds and `missing` is always empty. Keep `reference_dir` a directory the run never writes into, and arrange each case's presence by creating (or not) `reference_dir / f"{case.name}.md"` *before* the call. `run` calls `self._out_dir.mkdir(...)`; create `reference_dir` in the test (`mkdir`) so `Path.exists()` on its children resolves cleanly.
  Drive `EvalRunner.run` with `asyncio.run` (or a plain `async def test_...` — `pyproject.toml` sets `asyncio_mode = "auto"`, so both are auto-collected). Assert on captured stdout via `capsys`:
  - No case has a reference → summary names every case.
  - Some cases have references, some do not → summary names only the ones that do not.
  - Every case has a reference → summary names no case as missing.
  - Exit status / return is identical across all three (the call completes normally — `run` returns `None`, never raises — in every arrangement).

- [x] **Task 5: Document the reporting behavior in the eval-harness section of `CLAUDE.md`** (depends on Task 3)
  Files: `CLAUDE.md`
  In the `## Verification — eval harness` section, add a present-tense sentence stating that after writing every case's output the run prints a closing summary naming any case with no `evals/reference/<case>.md` and stating how many of how many cases had nothing to compare against, and that this is presence reporting only — non-fatal, so a missing note never breaks a run and does not change the exit status. Describe the behavior, not the code; do not reference the plan/roadmap or `.ai-factory/` paths.
