# 21.1 — Wire a `narrate` case into the eval harness

**Phase:** 21 — Ground truth for the eval harness. Independent of 21.2 and 21.3 — adds a case entry only, touches neither reference authoring nor the runner's reporting.

## Current state

`scripts/eval.py` already constructs `NarrateCaseHandler` at the composition root whenever a reasoner-family case is present in `evals/cases.yaml`, but no case there declares `type: narrate`. The handler is built and wired, and it is never dispatched to — narration has never been exercised by the harness at all.

## Change

Add a `narrate` case to `evals/cases.yaml`: `repo: "."`, `range: 0783684467d191a44bea94aa1de521f2cb23d6df..1bb7597925f54d42184d317c4f5eb2b2fde9aabe`, `lang: ru`, carrying the same kind of comment the other unreferenced cases already carry, noting that its comparison reference is user-authored and not yet created. The range is fixed rather than relative to `HEAD`, so the case's input does not move under its reference as new commits land on this repo.

## Files & types

- edit `evals/cases.yaml` (add one `narrate` case entry)

## Guards

- `NarrateCaseHandler.run` reads a singular `inputs["lang"]` (defaulting to `"ru"` when absent); the new case uses the singular `lang` key, never the plural `langs` key the localize handler expects — copying the localize case's key shape would be wrong here.
- Nothing is added under `evals/reference/` — this task adds case wiring only, never reference content.
- The chosen `repo`/`range` must resolve a genuine, non-empty linked change against this repository's own history, not an empty or synthetic range.
- No handler code and no runner code changes — `NarrateCaseHandler` and `EvalRunner` are both already correct; only the case list grows.

## Verification

- A harness run dispatches the new case to `NarrateCaseHandler` and writes its output under `evals/out/`.
- No other case's output changes as a result of this addition.
