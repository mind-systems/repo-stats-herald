# Plan Review: 07 — Eval harness

**Plan:** `.ai-factory/plans/07-eval-harness.md`
**Files Reviewed:** plan + targeted codebase (`scripts/summarize_range.py`, `src/commits/collector.py`, `src/summarization/service.py`, `src/llm/client.py`, `src/core/config.py`, `pyproject.toml`, `Makefile`, `.gitignore`, spec note `07-eval-harness.md`, `ROADMAP.md`, `ARCHITECTURE.md`)
**Risk Level:** 🟢 Low

## Context Gates

- **Architecture** (`ARCHITECTURE.md`): ✅ Aligned. `EvalRunner` as a thin composition-root driver in `scripts/` with constructor-injected `Summarizer`/`GitCommitCollector` and no prompt/git/HTTP logic matches the "composition root wires concretes; entry points only assemble and delegate" rule. The doc's Folder Structure already reserves `scripts/` "for offline runs (spike, eval)" and `evals/` "eval fixtures, references, outputs" — the plan lands exactly where the architecture anticipated it. Mild note below on the "logic in entry points" boundary.
- **Rules** (`.ai-factory/rules/*.md`): ✅ No violations. `snake_case.py`, `PascalCase` class, no secrets in committed files (`repo: .`, env-sourced Ollama config). The stale `rules/` module map (`src/routes`, `src/services`) is auto-detected boilerplate superseded by `ARCHITECTURE.md`'s feature-modular layout — not applicable.
- **Roadmap** (`ROADMAP.md`): ✅ Linked. Directly implements the active Phase 1 task "**Eval harness**" (task 07); scope, guards, and target files match the roadmap line and the spec note. No missing linkage.
- **Skill-context** (`.ai-factory/skill-context/aif-review/SKILL.md`): not present — no project overrides to apply.

## Critical Issues

None. Signatures, wiring, and file targets all check out against the real code:

- `collector.collect(case.repo, case.range)` matches `GitCommitCollector.collect(repo_path, rev_range)`.
- `await summarizer.summarize(ctx, case.lang)` matches `Summarizer.summarize(context, lang="ru") -> str` (async).
- Composition (`get_settings()` → `GitCommitCollector()` → `Summarizer(OllamaClient(url, model, api_key), PromptBuilder())`) mirrors `scripts/summarize_range.py` exactly.
- Dependency: `pyyaml` package → `import yaml` / `yaml.safe_load` is the correct name pairing; not currently in `pyproject.toml`.
- No DB touched → no migrations needed. Offline/local-git only → no new security surface.

## Non-Blocking Notes

1. **`-m scripts.eval` is the correct choice — the spec's verify command is not.** `scripts/` has no `__init__.py` and relies on Python 3.12 namespace packages plus cwd-on-path. Running `python -m scripts.eval` from the project root puts the root on `sys.path`, so `from src... import ...` resolves. The spec note's verify line `uv run python scripts/eval.py` (direct-file form) would put only `scripts/` on the path and break `import src`. The plan (Task 4 uses `-m scripts.eval`) silently corrects this — good. Keep the module form; do not fall back to the direct-file invocation.

2. **`__main__` guard is implied but not stated.** For `python -m scripts.eval` to actually call `main()`, the file needs `if __name__ == "__main__": main()` (as `summarize_range.py` has). The plan says "mirror the composition style of `scripts/summarize_range.py`," which covers it, but it's worth making explicit so the module isn't a no-op when run.

3. **Pin the `cases.yaml` shape once.** Task 2 allows "top-level list (or `cases:` key)" and Task 3 must parse whatever Task 2 emits. Same implementer, so low risk, but choose one shape and have `main()` parse that exact shape (e.g. if `yaml.safe_load` returns a `dict`, read `data["cases"]`; if a `list`, iterate directly). A one-line mismatch here is the most likely bug in the whole plan.

4. **`.gitignore` pattern is correct.** `evals/out/*` + `!evals/out/.gitkeep` keeps generated outputs untracked while persisting the directory. Confirmed the current `.gitignore` has no conflicting `evals/` rule.

5. **"Logic in entry points" boundary.** `ARCHITECTURE.md` lists collecting/summarizing inside a `scripts/*` file as an anti-pattern, but the spec note explicitly sanctions `EvalRunner` as a thin composition-root driver that only orchestrates injected feature objects (loop: collect → summarize → write). This is consistent as long as the runner adds no prompt/git/HTTP/parse logic of its own — the plan already states this constraint. No change needed; flagging only so the implementer keeps the loop strictly orchestration + file I/O.

6. **Logging setting = minimal.** The plan writes output files silently. A single per-case progress line (e.g. `print(f"{case.name} -> evals/out/{case.name}.md")`) would satisfy "minimal logging" and make the run observable without over-engineering. Optional.

## Positive Notes

- Correctly restricts seed fixtures to **this repo only** (`repo: .`, `HEAD~3..HEAD`), overriding the spec note's mention of external `mind`/`tradeoxy` paths that would be non-portable and non-runnable in CI/other machines.
- Honors the "references are user-authored, never fabricated" guard by scaffolding an empty `evals/reference/` via `.gitkeep` rather than generating placeholder reference notes.
- Reuses the real production `Summarizer`/`GitCommitCollector` via constructor DI, so the eval measures the actual path — no parallel reimplementation. This is the core intent of the task and the plan nails it.
- Sensible two-commit split (fixtures+dep, then runner+target) with each commit independently coherent.

The plan is solid and implementation-ready; all notes above are non-blocking refinements.

PLAN_REVIEW_PASS
