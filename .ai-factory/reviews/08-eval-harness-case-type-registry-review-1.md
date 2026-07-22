# Code Review: Eval harness case-type registry

**Files reviewed:** `scripts/eval.py`, `evals/cases.yaml`
**Risk level:** 🟢 Low

## Scope

Reviewed the full diff (`git diff HEAD`) and read `scripts/eval.py` in full plus the producer signatures it drives (`src/summarization/service.py`, `src/commits/collector.py`). The change generalizes the summarizer-only eval runner into a case-type registry per the plan and spec `52-eval-harness-case-types.md`.

## Correctness

- **Byte-identical `summary` output (spec's no-regression guard):** `SummaryCaseHandler.run` (`scripts/eval.py:65-67`) is a straight move of the old body — `collect(repo, range)` → `summarize(ctx, lang)`. Verified against ground truth: `GitCommitCollector.collect(repo_path, rev_range)` and `Summarizer.summarize(context, lang)` signatures match the calls. `EvalRunner.run` still writes to `_OUT_DIR / f"{case.name}.md"` with the same `encoding="utf-8"`. Output is unchanged for the existing cases.
- **Unregistered type errors clearly, never silently skipped:** Pre-flight validation (`scripts/eval.py:77-82`) scans *all* cases and raises `ValueError` listing each offending `name`/`type` **before** `mkdir` or any write — so a mistyped case cannot be masked by a partial run. The error propagates through `asyncio.run` in `main()` to a non-zero exit. Matches the spec guard exactly.
- **Loader is type-agnostic:** `_load_cases` (`scripts/eval.py:92-104`) collects `inputs` as the verbatim remainder bag, so future case types need no loader change. Missing `name`/`type` raise a clear `KeyError` naming the case — no silent skip.
- **Registry seam / composition root:** `EvalRunner` takes only `handlers: dict[str, CaseHandler]`; concretes are wired solely in `main()` (`scripts/eval.py:114-117`). Later producers add one registry entry without editing the runner. `CaseHandler(ABC)` follows the project's `LLMClient(ABC)` convention.
- **`cases.yaml`:** both cases gained `type: summary`; the `{repo, range, lang}` inputs are unchanged and flow through as the case's `inputs`.

## Runtime / edge considerations

- No external consumers of `Case`/`EvalRunner`/`_load_cases`; `Makefile` invokes only `python -m scripts.eval`. The refactor is self-contained — no missed migration or downstream update.
- A non-dict raw case entry would hit `"name" not in c` and still raise rather than silently pass — acceptable; the fixtures are dict-shaped and this is a hand-authored file.
- No security surface: offline, read-only git, no new I/O or untrusted input beyond the existing local YAML.

## Findings

None.

REVIEW_PASS
