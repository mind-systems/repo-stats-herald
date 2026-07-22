## Code Review Summary

**Files Reviewed:** 1 plan (`.ai-factory/plans/08-eval-harness-case-type-registry.md`), targeting `scripts/eval.py` + `evals/cases.yaml`
**Risk Level:** 🟢 Low

### Context Gates

- **Roadmap** (`ROADMAP.md:18` → `Spec: .ai-factory/specs/52-eval-harness-case-types.md`): ✅ Task is on the roadmap under Phase 1; the plan is a faithful decomposition of the contract line and the leaf spec. Every spec guard is carried into a concrete task:
  - byte-identical `summary` output → Task 3 ("straight move of the current `EvalRunner.run` body", "byte-identical") and Task 6 (inputs unchanged).
  - unregistered `type` errors clearly, never silently skipped → Task 4 pre-flight validation raising `ValueError` *before* any output is written.
  - registry is the seam, runner not edited per producer → Tasks 2 & 5.
  - references stay user-authored → Task 6 explicitly forbids fabricating references.
- **Architecture** (`.ai-factory/ARCHITECTURE.md`): ✅ Aligned. `CaseHandler(ABC)` follows the "abstraction at every seam / introduce an ABC when a second implementation is imminent" rule (later producers are the imminent second impls). `SummaryCaseHandler` receives `Summarizer`/`GitCommitCollector` via constructor DI, and the registry is assembled only in `main()` — the composition root. Handlers stay thin (delegate to the already-wired producer), respecting "logic in entry points" avoidance.
- **Rules** (`.ai-factory/RULES.md`): ✅ File is intentionally empty (no project counter-defaults); nothing to enforce.
- **Skill-context** (`.ai-factory/skill-context/aif-review/SKILL.md`): not present — no project-specific review overrides to apply.

### Verified against ground truth

- `scripts/eval.py` current shape matches the plan's "Current state" assumptions exactly: `Case(name, repo, range, lang)` frozen/slots dataclass, `EvalRunner(summarizer, collector)`, `run` doing collect → summarize → `write_text` → `print`, `_load_cases()` tolerating both a `cases:` mapping and a bare list. Task 1's proposed `_load_cases` rewrite and Task 3's `run` body reproduction are both accurate transcriptions.
- `src/llm/client.py` confirms the ABC convention Task 2 cites (`LLMClient(ABC)` + `@abstractmethod async def`). The proposed `CaseHandler` mirrors it correctly.
- `Summarizer.summarize(context, lang)` and `GitCommitCollector.collect(repo_path, rev_range)` signatures match the calls Task 3 specifies (`collect(inputs["repo"], inputs["range"])`, `summarize(ctx, inputs["lang"])`).
- **No external consumers:** a repo-wide grep found no importer of `Case`, `EvalRunner`, `_load_cases`, or `CaseHandler` outside `scripts/eval.py`, and `Makefile` invokes only `python -m scripts.eval`. The refactor is fully self-contained — no migration or downstream update is missed.

### Critical Issues

None. File paths, API signatures, DI wiring, and the task dependency chain (1→2→3→4→5; 6 depends on 1) are all correct and match the codebase.

### Positive Notes

- Pre-flight validation in Task 4 (collect all unregistered types and raise *before* `mkdir`/writing) is the right design — it satisfies the spec's "no partial run masking a mistyped case" guard rather than failing mid-loop.
- Task 3 explicitly pins "byte-identical output / straight move of the body," which is exactly how to keep the `summary` cases regression-free through the harness.
- Keeping `inputs` as a verbatim `{k: v for k, v in c.items() if k not in ("name","type")}` bag means later case types need no `_load_cases` change — the loader is already type-agnostic, matching the "runner never edited per producer" intent.

## Deferred observations

- Affects: later prose-producer phases (5.2.2 distiller, 7.1.2 reasoner, 8.1 narrate, 10.1.2 report, 11.2.2 release) — The spec says each later producer's `CaseHandler` "registration lives with the producer." Because `CaseHandler` (the ABC) lands in `scripts/eval.py` (composition-root/eval layer), those future handler subclasses should also live in the eval/scripts layer, not inside their `src/` feature packages — a `src/` feature subclassing an ABC defined in `scripts/` would invert the architecture's dependency rule (features must not depend on the composition root). This is a future-phase wiring decision, out of this task's scope; no action needed now, but the phase that adds the second handler should keep handler classes on the eval side of the boundary.

PLAN_REVIEW_PASS
