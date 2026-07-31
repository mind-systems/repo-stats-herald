# Review: 21.1 — Wire a `narrate` case into the eval harness

## Scope
Single change: one case entry appended to `evals/cases.yaml`. No code changes to `scripts/eval.py` or any handler/runner. Verified `git status`/`git diff HEAD` — the only tracked source change is `evals/cases.yaml`; the rest are `.ai-factory/` planning artifacts.

## Verification performed
- **Parses & dispatches:** `scripts.eval._load_cases()` produces `Case(name='herald-narrate', type='narrate', inputs={'repo': '.', 'range': '0783684...1bb7597', 'lang': 'ru'})`. `type='narrate'` is a registered handler and is one of `("reasoner", "narrate", "localize")` at scripts/eval.py:214, so the DB pool is created and `NarrateCaseHandler` is wired and dispatched to.
- **Key shape correct (guard):** the entry uses singular `lang: ru`, which is exactly what `NarrateCaseHandler.run` reads (`inputs.get("lang", "ru")`, scripts/eval.py:127). The plural `langs` list form belonging to `LocalizeCaseHandler` was correctly avoided.
- **Reference pairing (guard):** `evals/reference/herald-narrate.md` exists; `name` is pinned to `herald-narrate`, so `EvalRunner` pairs the case to that reference and writes `evals/out/herald-narrate.md`. No file added under `evals/reference/`.
- **Range resolves a genuine, non-empty change (guard):** `git rev-list --count` for the range returns 3 commits (`366e882..1bb7597`); the range is a fixed literal commit pair, not `HEAD`-relative, so it will not drift. `_split_range` splits it cleanly into before/after.
- **No collateral effects:** the entry is appended at the end of the list; no other case entry is altered, so no other case's output changes.

## Findings
None. The change matches the spec (`.ai-factory/specs/62-narrate-eval-case.md`) exactly, all four guards hold, and it loads and dispatches correctly.

REVIEW_PASS
