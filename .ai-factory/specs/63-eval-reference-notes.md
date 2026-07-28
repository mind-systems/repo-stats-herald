# 21.2 — Author the eval reference notes (manual)

**Phase:** 21 — Ground truth for the eval harness. Independent of 21.1 and 21.3.

**This is a manual task. No agent executes it and no agent generates its content. An orchestrator that picks this task up must stop and leave every file unchanged.**

## Current state

`evals/reference/` holds only `.gitkeep`. Not one case in `evals/cases.yaml` has a reference note, so every harness run produces output with nothing to compare it against, and the harness measures nothing — despite the project's stated discipline that quality is checked against fixed cases rather than eyeballed. Authoring a reference note is only meaningful once each case's input is fixed, so the range-pinning task lands first — otherwise the note describes commits the case no longer covers.

## Change

The repository owner writes one reference note by hand, per case, at `evals/reference/<case>.md`, named to match the case names in `evals/cases.yaml`. A reference is what the producer *should* have written for that case — a hand-judged standard of quality. A generated reference would measure the model against itself, which is the exact failure this harness exists to prevent.

## Files & types

- add `evals/reference/<case>.md` for each case in `evals/cases.yaml`, written by hand by the repository owner — no file listed here is ever touched by an agent

## Guards

- No agent authors, drafts, seeds, or "starts" a reference note under any circumstance, including copying or lightly editing a harness output as a starting point.
- The task is complete only when every reference note exists and a person wrote it — not when a placeholder exists, and not when an agent's draft exists.
- The case list this task covers is whatever `evals/cases.yaml` holds at the time the notes are written, including the `narrate` case once it exists.

## Verification

- Every case named in `evals/cases.yaml` has a corresponding file under `evals/reference/`.
- Each of those files was written by a person, not generated.
