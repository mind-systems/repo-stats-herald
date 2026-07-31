# Plan: 21.1 — Wire a `narrate` case into the eval harness

## Context
Add a `narrate` case to `evals/cases.yaml` so the already-wired `NarrateCaseHandler` is actually dispatched to, exercising the LinkedChangeResolver + Reasoner.narrate flow against a fixed slice of this repo's own history paired with the existing `evals/reference/herald-narrate.md`.

## Settings
- Testing: no
- Logging: minimal
- Docs: no

## Tasks

### Phase 1: Add the case entry

- [x] **Task 1: Append the `herald-narrate` case to `evals/cases.yaml`**
  Files: `evals/cases.yaml`
  Add one new case entry at the end of the `cases:` list, following the block style and two-space list indentation of the existing entries. The entry must be exactly:

  ```yaml
  - name: herald-narrate
    type: narrate
    repo: "."
    range: 0783684467d191a44bea94aa1de521f2cb23d6df..1bb7597925f54d42184d317c4f5eb2b2fde9aabe
    lang: ru
  ```

  Key points, all mandated by the spec (`.ai-factory/specs/62-narrate-eval-case.md`):
  - Use the **singular** `lang: ru` key — `NarrateCaseHandler.run` (scripts/eval.py:124-127) reads `inputs.get("lang", "ru")`. Do **not** use the plural `langs:` list form that the `herald-localize` case uses; that key shape belongs only to `LocalizeCaseHandler`.
  - `name` is pinned to `herald-narrate` because `evals/reference/herald-narrate.md` already exists and `EvalRunner` pairs a case to its reference by name alone. Any other name would orphan that reference.
  - The `range` is the fixed literal commit-pair above (verified to resolve a genuine non-empty 3-commit slice of this repo: `366e882..1bb7597`), not a `HEAD`-relative range, so the case's input does not drift under its reference as new commits land.
  - Optionally match the surrounding style by adding a short `#` comment above the entry (as the other reasoner-family cases have), noting the reference is user-authored and the name/range are pinned. Keep it brief; this is cosmetic and not required.

  Do **not**: add anything under `evals/reference/`, edit any handler or runner code in `scripts/eval.py`, or change any other case entry. The handler and runner are already correct — only the case list grows.
