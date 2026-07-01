# Eval Harness — Measuring Summary Quality

**Date:** 2026-07-01
**Source:** conversation context

## Key Findings

- Once a summary can be produced, quality can only be eyeballed once. Changing the prompt or the model has no objective signal.
- This task adds an offline eval harness: a fixed set of `{repo, range}` cases run through the `Summarizer`, with outputs written next to human-approved reference notes for side-by-side review. This turns "decent notes" from a hope into a repeatable loop.

## Details

### Current state
Task 06 gives a one-shot CLI. There is no fixture set and no way to re-run the same inputs after a prompt change.

### Target
- `evals/cases.yaml` (or `.json`) — the fixture set: a list of `{name, repo, range, lang}` entries pointing at real ranges in local repos (this repo, mind, tradeoxy).
- `evals/reference/<case>.md` — optional human-approved "good" notes per case (the quality fuel; supplied by the user, not generated).
- `evals/out/<case>.md` — generated output, git-ignored or kept for diffing.
- `scripts/eval.py` with an `EvalRunner`:
  ```python
  class EvalRunner:
      def __init__(self, summarizer: Summarizer, collector: GitCommitCollector) -> None: ...
      async def run(self, cases: list[Case]) -> None:
          # for each case: collect -> summarize -> write evals/out/<name>.md
  ```
  Reuses the exact same `Summarizer` / `GitCommitCollector` as the spike CLI (same composition, different driver).

### Architecture notes
`EvalRunner` is another composition-root-level driver, not a new layer — it depends on the same feature objects. Keeping it thin ensures the eval measures the real production path, not a parallel reimplementation. The reference notes are the seed of the "Quality feedback loop" phase: approved outputs get promoted into `evals/reference/` and later fed back as few-shot examples.

### Guards
- Offline and deterministic in structure — one output file per case, stable filenames for diffing across prompt versions.
- Reference notes are authored by the user; the harness never fabricates a "reference".
- Do not couple to a scoring model yet — human side-by-side review is the judge for now.

### Verify
- `uv run python scripts/eval.py` (tunnel up) produces exactly one `evals/out/<case>.md` per case in `evals/cases.yaml`, each containing a non-empty summary.

## Open Questions

- Needs 3–5 real commit ranges with user-approved reference notes to be genuinely useful — the user agreed to supply these.
- Automated scoring (LLM-as-judge against the reference) is deferred to the Quality feedback loop phase; not part of this task.
