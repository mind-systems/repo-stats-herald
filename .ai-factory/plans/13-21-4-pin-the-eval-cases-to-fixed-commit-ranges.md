# Plan: 21.4 — Pin the eval cases to fixed commit ranges

## Context
Replace the `HEAD~3..HEAD` moving range in the three range-bearing eval cases with a fixed commit pair so each case's input window is stable across new commits, keeping outputs aligned with their already-authored reference notes.

## Settings
- Testing: no
- Logging: minimal
- Docs: no

## Tasks

### Phase 1: Pin the ranges

- [x] **Task 1: Replace the moving range in the three affected cases**
  Files: `evals/cases.yaml`
  In the three cases that declare `range: HEAD~3..HEAD` — `herald-recent` (lang `ru`), `herald-recent-en` (lang `en`), and `herald-localize` (langs `[en, ru]`) — replace each `range` value with the fixed `0783684467d191a44bea94aa1de521f2cb23d6df..1bb7597925f54d42184d317c4f5eb2b2fde9aabe`. Change only the `range` value on each case; do not touch any other field (`name`, `type`, `repo`, `lang`, `langs`). Mirror the already-pinned `herald-narrate` case (same repo, same fixed range) as the pattern to match. Add a short comment above the pinned cases explaining that the range is a fixed commit pair (not `HEAD`-relative) so the input window does not drift under its user-authored reference note, mirroring the existing `herald-narrate` comment — this prevents a future edit from "modernizing" it back to `HEAD`.

  Guards to honor: case names stay identical (no output/reference filename moves); the two rangeless cases `mind-features` and `herald-self-query` are untouched; no reference note is authored or seeded here.
