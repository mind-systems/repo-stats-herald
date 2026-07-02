# Code Review: 07 — Eval harness (round 2)

**Scope:** `git diff HEAD` — `scripts/eval.py`, `evals/cases.yaml`, `evals/{out,reference}/.gitkeep`, `.gitignore`, `Makefile`, `pyproject.toml`, `uv.lock`.

## Summary

Both findings from round 1 have been addressed:

1. **UTF-8 encoding** — `scripts/eval.py:51` now uses `out_path.write_text(summary, encoding="utf-8")`, so Russian/English summaries write correctly regardless of host locale. ✅
2. **Empty/malformed `cases.yaml`** — `_load_cases` now guards `None` from `yaml.safe_load` with `(data or {}).get("cases", []) if isinstance(data, dict) else (data or [])`, avoiding the opaque `TypeError`. ✅

## Verification

Re-confirmed against source — all correct:

- `self._collector.collect(case.repo, case.range)` ↔ `GitCommitCollector.collect(repo_path, rev_range)`
- `await self._summarizer.summarize(ctx, case.lang)` ↔ `Summarizer.summarize(context, lang="ru") -> str` (async)
- `Summarizer(OllamaClient(url, model, api_key), PromptBuilder())` ↔ real constructors; composition mirrors `scripts/summarize_range.py`
- `pyyaml` in `pyproject.toml` + `uv.lock`; `import yaml` / `yaml.safe_load` name pairing correct
- Path resolution via `Path(__file__).resolve().parent.parent / "evals"` is cwd-independent
- `cases.yaml` uses the `cases:` dict shape, matched by `_load_cases`
- `.gitignore` (`evals/out/*` + `!evals/out/.gitkeep`) and Makefile `eval: tunnel` target correct
- `__main__` guard present; runs as `python -m scripts.eval`

No remaining findings.

REVIEW_PASS
