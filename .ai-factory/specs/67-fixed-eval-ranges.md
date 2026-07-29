# 21.4 — Pin the eval cases to fixed commit ranges

**Phase:** 21 — Ground truth for the eval harness. Must land before any harness run — the reference notes are already authored against the fixed window, so until the cases are pinned a run reports differences that are not quality problems.

## Current state

Three cases declare a range relative to `HEAD`. The harness resolves it at run time, so the same case name covers different commits on different days. Nothing in the harness or the case file records which commits a given output described, so an output and a reference can silently describe different change sets. Two cases are unaffected — one reads a fixed local checkout, the other asks a fixed question — though the second's answer still depends on what has been indexed into the stores, which is a separate concern and out of scope here.

## Change

Replace the relative range in the three affected cases with the fixed `0783684467d191a44bea94aa1de521f2cb23d6df..1bb7597925f54d42184d317c4f5eb2b2fde9aabe` — three commits that each flip one roadmap task to `[x]`, so a linked change resolves non-empty — and add a short comment in the case file recording why the range is pinned rather than relative, so a future edit does not helpfully "modernize" it back to `HEAD`.

## Files & types

- edit `evals/cases.yaml` (`herald-recent`, `herald-recent-en`, `herald-localize`)

## Guards

- Case names do not change, so no output or reference filename moves.
- Only the `range` values change — no case gains, loses, or alters any other field.
- The two rangeless cases (`mind-features`, `herald-self-query`) are untouched.
- No reference note is authored or seeded by this task — that stays manual.

## Verification

- The same case produces the same input window on two runs separated by new commits to this repo.
- The pinned range resolves a non-empty linked change.
- Every case still dispatches to its registered handler.
