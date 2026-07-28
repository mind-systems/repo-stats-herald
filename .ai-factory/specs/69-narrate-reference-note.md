# 21.5 — Author the narrate reference note (manual)

**Phase:** 21 — Ground truth for the eval harness. Depends on 21.1 (the `narrate` case must exist first).

**This is a manual task. No agent executes it and no agent generates its content. An orchestrator that picks this task up must stop and leave every file unchanged.**

## Current state

Reference notes exist for every case that was present when they were authored. A `narrate` case is added separately, and the task that adds it is forbidden to write anything under `evals/reference/`, so on landing it produces output with nothing to compare against — the same blindness the harness's reporting task exists to surface, reappearing for this one case.

## Change

The repository owner writes the `narrate` case's reference note by hand, once the case exists.

## Files & types

- add `evals/reference/<case>.md` for the `narrate` case, written by hand by the repository owner — this file is never touched by an agent

## Guards

- The case must exist first — this task depends on 21.1.
- No agent authors, drafts, seeds, or lightly edits the note under any circumstance, including from a harness output.
- The five existing reference notes are out of scope for this task — neither touched, reviewed, nor regenerated.
- The task is complete only when the note exists and a person wrote it.

## Verification

- The `narrate` case has a reference file under `evals/reference/`.
- It was written by a person, not generated.
