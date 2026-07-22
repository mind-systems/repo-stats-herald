# Plan: Eval harness case-type registry

## Context
Generalize `scripts/eval.py` + `evals/cases.yaml` from a summarizer-only runner into a case-type registry: each case declares a `type`, the runner dispatches to a registered `CaseHandler` that runs the same composition-root producer and writes `evals/out/<name>.md`. Ship the `summary` handler (today's behavior refactored, output-identical) so later prose producers each register their own handler without editing the runner.

## Settings
- Testing: no
- Logging: minimal

## Tasks

### Phase 1: Registry seam and summary handler in `scripts/eval.py`

- [x] **Task 1: Generalize the `Case` model to carry a type + type-specific inputs**
  Files: `scripts/eval.py`
  Replace the fixed `Case(name, repo, range, lang)` dataclass with a type-agnostic shape: `Case(name: str, type: str, inputs: dict)` (frozen, slots) — `name` is the stable output filename, `type` selects the handler, `inputs` holds the remaining type-specific fields verbatim. Update `_load_cases()` to read each raw case as `name = c["name"]`, `type = c["type"]`, and `inputs = {every other key}` (e.g. `{k: v for k, v in c.items() if k not in ("name", "type")}`). Keep the existing tolerance for either a top-level `cases:` mapping or a bare list. A case missing `name` or `type` raises a clear `KeyError`/`ValueError` naming the offending case — never a silent skip.

- [x] **Task 2: Add the `CaseHandler` seam** (depends on Task 1)
  Files: `scripts/eval.py`
  Define an abstract base `CaseHandler(ABC)` with one async method `run(self, inputs: dict) -> str` — given a case's inputs, it builds the producer's call, runs the already-wired composition-root producer object, and returns the produced text. Follow the project's existing ABC convention (`LLMClient(ABC)` in `src/llm/client.py`) — a plain abstract class, `@abstractmethod` on `run`. The handler owns no output-file or filename logic (that stays in `EvalRunner`); it is purely inputs → text. Document in the docstring that each later producer ships its own `CaseHandler` and registers it at the composition root — the runner is never edited per producer.

- [x] **Task 3: Implement the `summary` handler** (depends on Task 2)
  Files: `scripts/eval.py`
  Add `SummaryCaseHandler(CaseHandler)` taking `Summarizer` and `GitCommitCollector` via constructor DI (the same objects the composition root already builds). Its `run(inputs)` reproduces today's behavior exactly: `ctx = self._collector.collect(inputs["repo"], inputs["range"])` then `return await self._summarizer.summarize(ctx, inputs["lang"])`. The logic must be a straight move of the current `EvalRunner.run` body so a `summary` case yields byte-identical output (no regression). A missing `repo`/`range`/`lang` key raises a clear `KeyError`.

- [x] **Task 4: Turn `EvalRunner` into a registry dispatcher** (depends on Task 3)
  Files: `scripts/eval.py`
  Change `EvalRunner.__init__` to take a registry `handlers: dict[str, CaseHandler]` instead of `(summarizer, collector)`. In `run(cases)`: first **pre-flight validate** — collect every case whose `type` is not in `self._handlers` and, if any exist, raise a clear `ValueError` listing the unregistered type(s) and case name(s) **before** writing any output, so a mistyped case is never masked by a partial run. Then `mkdir` the out dir, and for each case dispatch to `self._handlers[case.type].run(case.inputs)`, writing the text to `_OUT_DIR / f"{case.name}.md"` (unchanged filename convention) and printing `wrote {out_path}` as today. The raised error propagates through `asyncio.run` in `main` to a non-zero exit.

- [x] **Task 5: Wire the registry at the composition root** (depends on Task 4)
  Files: `scripts/eval.py`
  In `main()`, keep building `settings`, `GitCommitCollector`, and `Summarizer(OllamaClient(...), PromptBuilder())` exactly as now, then assemble the registry `{"summary": SummaryCaseHandler(summarizer, collector)}` and pass it to `EvalRunner(handlers)`. This is the single place a case type maps to a concrete producer — later producers add their `type: handler` entry here. Update the module docstring so it describes the runner as a type-dispatching registry, not a summarizer-only harness.

### Phase 2: Case fixtures

- [x] **Task 6: Add `type: summary` to the existing cases** (depends on Task 1)
  Files: `evals/cases.yaml`
  Give each existing case a `type: summary` field alongside its `name`/`repo`/`range`/`lang` (the `{repo, range, lang}` inputs are unchanged and become the case's type-specific inputs). These stay the only shipped cases — later producers append their own typed cases when built. Do not add unregistered-type cases; references remain user-authored and are never fabricated here.
