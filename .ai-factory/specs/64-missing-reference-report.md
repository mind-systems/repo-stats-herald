# 21.3 — Report eval cases with no reference

**Phase:** 21 — Ground truth for the eval harness. Independent of 21.1. The reference notes are already authored, so the report finds nothing missing today — its value is standing: a case added later without a note, or a note removed, becomes loud instead of silent.

## Current state

`EvalRunner.run` writes `evals/out/<case>.md` per case and prints `wrote <path>`, with no check of whether the matching reference file exists. A run that measures nothing today looks identical, line for line, to a run that measures everything — nothing about the harness's own output distinguishes the two.

## Change

After the per-case writes, check each case for its matching file under `evals/reference/`, and print a closing summary naming every case that has none, stating the count plainly — how many of how many cases had nothing to compare against. Update the eval-harness section of the project's own root instructions to state this reporting behavior as part of what `make eval` does.

The new check follows the same shape as the existing validation already at the top of `EvalRunner.run`: enumerate the cases, collect the ones that fail the condition — here, missing a reference file, rather than an unregistered case type — and report them once in a single message rather than per case; unlike that existing check, this one stays non-fatal rather than raising. The reference path for a case derives from a reference directory exactly as its output path already derives from the output directory, so the two stay symmetric and a case's reference is always found where its output is written.

## Files & types

- edit `scripts/eval.py` (`EvalRunner.run`)
- edit `CLAUDE.md` (the eval-harness verification section)
- new `tests/scripts/test_eval.py` (drives `EvalRunner.run` directly with a stub handler and temporary output/reference directories; the harness's first test module)

## Guards

- Non-fatal: every output is still written, and the process exit status is unchanged, so a case without a note never breaks a run.
- Presence checking only — this task adds no diffing, scoring, or judging logic of any kind.
- The existing per-case `wrote <path>` line is untouched; the summary is additive, printed once at the end of the run.

## Verification

This harness has no test module today; this task adds its first. `tests/scripts/test_eval.py` drives `EvalRunner.run` directly with a stub `CaseHandler` and with the output and reference directories pointed at temporary paths, so each of the four criteria below is arranged by which temp files exist before the call — no live model call, no SSH tunnel, and no authored reference required for any of them.

- A run where no case has a reference prints a summary naming every case.
- A run where some cases have references and some do not names only the ones that do not.
- A run where every case has a reference states that plainly, with no case named as missing.
- The process exit status is identical across all three of the above.
