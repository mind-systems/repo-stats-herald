# Plan: Eval harness

## Context
Add an offline eval harness so summary quality has a repeatable signal: fixed `{repo,range,lang}` cases run through the exact production `Summarizer`/`GitCommitCollector`, writing one stable-named output file per case next to user-authored reference notes for side-by-side diffing.

## Settings
- Testing: no
- Logging: minimal
- Docs: no

## Tasks

### Phase 1: Fixtures & dependency

- [x] **Task 1: Add YAML parsing dependency**
  Files: `pyproject.toml`
  Add `pyyaml` to the `dependencies` list (the harness reads `evals/cases.yaml`; no YAML parser is currently available). Keep the alphabetical-ish ordering consistent with the existing list. After this, `uv sync` will pull it in.

- [x] **Task 2: Create the fixture set and reference/output scaffolding**
  Files: `evals/cases.yaml`, `evals/reference/.gitkeep`, `evals/out/.gitkeep`, `.gitignore`
  Create `evals/cases.yaml` as a top-level list (or `cases:` key) of entries with fields `name`, `repo`, `range`, `lang`. Seed 1–2 example cases pointing at safe local ranges in **this** repo only (e.g. `name: herald-recent`, `repo: .`, `range: HEAD~3..HEAD`, `lang: ru`) as runnable placeholders — do NOT invent external repo paths. Add `evals/reference/.gitkeep` (references are user-authored, never fabricated — leave the directory empty otherwise) and `evals/out/.gitkeep`. In `.gitignore` add `evals/out/*` with `!evals/out/.gitkeep` so generated outputs stay untracked but the directory persists. Reference notes stay tracked.

### Phase 2: Runner

- [x] **Task 3: Implement the eval runner** (depends on Task 1, Task 2)
  Files: `scripts/eval.py`
  Add an `EvalRunner` plus a `Case` dataclass (fields `name`, `repo`, `range`, `lang`). `EvalRunner.__init__(self, summarizer: Summarizer, collector: GitCommitCollector)` stores injected collaborators — no concretes built inside. `async def run(self, cases: list[Case]) -> None`: for each case, `collector.collect(case.repo, case.range)` → `await summarizer.summarize(ctx, case.lang)` → write the result to `evals/out/<case.name>.md` (create the dir if missing, overwrite for stable diffable filenames). Keep runner thin: no prompt/git/HTTP logic, just orchestration — mirror the composition style of `scripts/summarize_range.py`. Add a `parse_args`-free `main()` composition root that reads `evals/cases.yaml` (via `yaml.safe_load`), builds each `Case`, wires `Settings → GitCommitCollector → Summarizer(OllamaClient(...), PromptBuilder())` exactly as `scripts/summarize_range.py` does, and runs `asyncio.run(runner.run(cases))`. Guard: offline/local git only, no scoring model. Reuse the real production objects — do not reimplement collection or summarization.

- [x] **Task 4: Add the `eval` Make target** (depends on Task 3)
  Files: `Makefile`
  Add an `eval` target (and to `.PHONY`) that depends on `tunnel` and runs `uv run python -m scripts.eval` — matching the `dev` target's pattern so Ollama is reachable before the run.

## Commit Plan
- **Commit 1** (after tasks 1-2): "Add eval fixtures and yaml dependency"
- **Commit 2** (after tasks 3-4): "Add eval runner and make target"
