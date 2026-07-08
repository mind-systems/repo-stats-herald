# Eval harness case-type registry

**Phase:** 1 — Summarizer spike & eval harness. Extends task 07 (the eval harness) so it verifies every prose producer, not only the summarizer. It is producer-agnostic infrastructure — it defines the dispatch seam and ships the summary handler, without depending on producers that land in later phases (each of those registers its own handler when it is built).

## Current state

`scripts/eval.py`'s `EvalRunner(summarizer: Summarizer, collector: GitCommitCollector)` is hardwired to the summarizer: a case in `evals/cases.yaml` is `{name, repo, range, lang}`, and `run` does collect → `Summarizer.summarize` → write `evals/out/<name>.md`. Every prose producer added since references "verify through the eval harness against a user-authored reference," but with a different case shape the runner cannot dispatch:
- code distiller (5.2.2) — `{repo, paths}` → feature text
- reasoner (7.1.2) — `{repo, query}` → answer
- `narrate` (8.1) — `{change, lang}` → note
- report sections (10.1.2) — `{repo, schedule/window}` → report
- release note (11.2.2) — `{repo, branch}` → release note over the deploy accumulation

Those verification claims cannot be cashed against the current runner.

## Change

Generalize the harness to a **case-type registry** — the runner dispatches by case type to a registered handler, so a new producer adds a handler, never a new runner.

- `evals/cases.yaml` — each case gains a `type` field (`summary`, `distill`, `reason`, `narrate`, `report`, `release`, …) alongside its type-specific inputs. The existing `{name, repo, range, lang}` cases become `type: summary`.
- `scripts/eval.py`:
  - a `CaseHandler` seam — given a case's inputs, build the producer's call, run it, return the text. Each handler is thin: it wires the same composition-root producer object the production path uses (no parallel reimplementation).
  - `EvalRunner` holds a registry `type -> CaseHandler`; `run` dispatches each case to its handler and writes `evals/out/<name>.md`. Ship the `summary` handler (today's collect→summarize behavior, refactored onto the registry).
  - Each later producer registers its own `CaseHandler` at the composition root as part of that producer's verification wiring — the registration lives with the producer, not here.

## Files & types

- edit `scripts/eval.py` (`CaseHandler` seam, `EvalRunner` registry + dispatch, the `summary` handler)
- edit `evals/cases.yaml` (each case carries a `type`)

## Guards

- Offline, deterministic structure — one `evals/out/<name>.md` per case, stable filenames for diffing across prompt/model versions (unchanged from task 07).
- References are **user-authored**, never fabricated by the harness.
- **The `summary` case-type produces output identical to task 07** — refactoring onto the registry must not regress the existing cases.
- The registry is the seam: a new producer registers a handler; the runner is not edited per producer.
- **An unregistered case `type` errors clearly** (raises / non-zero exit), never silently skipped — a mistyped case that produced no eval output would look like a passing producer with no signal.
- No scoring model yet — human side-by-side review remains the judge (task 07's discipline).

## Verification

- The existing `{repo, range, lang}` summary cases run as `type: summary` and produce identical `evals/out/<case>.md`.
- A second registered case-type dispatches correctly and writes its output.
- A case with an unregistered `type` → a clear error, no silent skip, no partial run masking it.
