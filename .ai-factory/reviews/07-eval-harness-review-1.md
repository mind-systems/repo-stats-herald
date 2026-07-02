# Code Review: 07 — Eval harness

**Scope:** `git diff HEAD` — `scripts/eval.py`, `evals/cases.yaml`, `evals/{out,reference}/.gitkeep`, `.gitignore`, `Makefile`, `pyproject.toml`, `uv.lock`.

## Summary

The implementation matches the plan and reuses the real production `Summarizer`/`GitCommitCollector` via constructor DI, exactly as `scripts/summarize_range.py` does. All call signatures verified against source:

- `self._collector.collect(case.repo, case.range)` ↔ `GitCommitCollector.collect(repo_path, rev_range)` ✅
- `await self._summarizer.summarize(ctx, case.lang)` ↔ `Summarizer.summarize(context, lang="ru") -> str` (async) ✅
- `Summarizer(OllamaClient(url, model, api_key), PromptBuilder())` ↔ real constructors ✅
- `pyyaml` package → `import yaml` / `yaml.safe_load` name pairing correct; present in `pyproject.toml` and `uv.lock` ✅
- Path resolution via `Path(__file__).resolve().parent.parent / "evals"` is cwd-independent — robust regardless of where `make eval` runs ✅
- `cases.yaml` uses the `cases:` dict shape; `_load_cases` handles both dict-with-`cases` and bare-list forms — no shape mismatch ✅
- `.gitignore` (`evals/out/*` + `!evals/out/.gitkeep`) and Makefile `eval: tunnel` target are correct ✅

No blocking bugs. Two low-severity findings below.

## Findings

### 1. `write_text(summary)` uses locale encoding, not UTF-8 — can crash on non-UTF-8 systems (Low)

`scripts/eval.py:51` — `out_path.write_text(summary)` omits `encoding=`. `Path.write_text` defaults to `locale.getpreferredencoding()`. Summaries are explicitly generated in Russian (and English), so on any host whose preferred encoding is not UTF-8 (e.g. a Windows/CI runner using cp1252), writing Cyrillic output raises `UnicodeEncodeError` and the eval run dies mid-loop. On the current macOS dev box this happens to work, but the harness is meant to be re-run across machines/CI for prompt-vs-prompt diffing.

Recommendation: `out_path.write_text(summary, encoding="utf-8")`.

### 2. Empty/malformed `cases.yaml` yields an unclear `TypeError` (Low, defensive)

`scripts/eval.py:60-65` — if `cases.yaml` is empty (or contains only comments), `yaml.safe_load` returns `None`; `data["cases"] if isinstance(data, dict) else data` then passes `None` into the list comprehension, raising `TypeError: 'NoneType' object is not iterable` rather than a clear "no cases" message. Not reachable with the committed fixture, so purely defensive. Optional: guard with `raw_cases = (data or {}).get("cases", []) if isinstance(data, dict) else (data or [])` or an explicit error.

## Notes (non-blocking)

- `Case.name` is interpolated straight into the output filename (`_OUT_DIR / f"{case.name}.md"`). Since cases are user-authored fixtures (not untrusted input), this is acceptable; just be aware a `name` containing `/` or `..` would write outside `evals/out/`.
- `print(f"wrote {out_path}")` satisfies the plan's "minimal logging" setting — good, run is observable without over-engineering.
- Honors the "references user-authored, never fabricated" guard: `evals/reference/` scaffolded empty via `.gitkeep`, no generated reference notes.
