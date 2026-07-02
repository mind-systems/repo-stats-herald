# Plan Review: 05 — summarization/ feature

## Code Review Summary

**Files Reviewed:** plan `05-summarization-feature.md` + spec note `05`, against `src/commits/models.py`, `src/commits/collector.py`, `src/llm/client.py`, `src/core/config.py`, `ARCHITECTURE.md`, `ROADMAP.md`, `rules/base.md`
**Risk Level:** 🟢 Low

### Verified Assumptions (all correct)

- `CommitContext(repo, branch, commits: tuple[Commit, ...])` — matches `src/commits/models.py`.
- `Commit(sha, author, message, changed_files: tuple[str, ...], diffstat)` — matches `models.py`.
- The claim that `commit.message` already combines subject + body is **confirmed** by `collector.py:74` (`message = subject if not body else f"{subject}\n\n{body}"`). Using `commit.message` directly is right.
- `LLMClient` ABC with `async def generate(self, prompt: str) -> str` and `OllamaClient` — matches `src/llm/client.py`. `Summarizer.summarize` correctly `await`s `generate`.
- Import paths (`src.commits.models`, `src.llm.client`, `src.summarization.prompt`) are all valid.
- File paths (`src/summarization/{__init__,prompt,service}.py`) are correct and mirror the existing feature layout.
- No DB touched → no migrations needed (correct; this feature is pure in-process logic).

### Context Gates

- **Architecture (ARCHITECTURE.md):** ✅ Fully aligned. The plan honors feature-modular boundaries, constructor DI, dependence on the abstract `LLMClient` (not `OllamaClient`), prompt text kept inside `PromptBuilder`, and no env reads / no concrete-client construction inside the feature (wiring deferred to composition root, task 06). The plan even matches the exact `Summarizer` shape shown in ARCHITECTURE.md §"Layer / Feature Communication".
- **Rules (rules/base.md):** ⚠️ WARN — `base.md` describes a layer-first structure (`src/routes/`, `src/services/`, `src/models/`) that contradicts the feature-modular `ARCHITECTURE.md`. The plan correctly follows ARCHITECTURE.md, which is the authoritative, more recent doc (`base.md` is self-labeled "Auto-detected conventions. Edit as needed"). No action needed for this plan; the stale `base.md` is a project-hygiene note, not a plan defect.
- **Roadmap (ROADMAP.md):** ✅ Linked. The plan maps 1:1 to the active task "summarization/ feature" (Phase 1), including its guards (constructor DI, prompt text isolated, `lang` defaults to `ru`).

### Critical Issues

None. No missing steps, wrong assumptions, architectural mistakes, missing migrations, security holes, or incorrect paths/API usage.

### Minor / Non-Blocking Suggestions

These are optional refinements, not defects — the implementer may address them at their discretion.

1. **Empty-commit-tuple behavior (edge case).** The `commits/` roadmap guard states empty ranges must not crash. `PromptBuilder.build` should degrade gracefully when `context.commits == ()` (e.g. still emit a valid, if empty, prompt rather than an oddly-shaped one). Worth a single sentence in Task 2, though the LLM boundary itself won't crash on it.

2. **Prompt-injection awareness (low risk, internal tool).** Commit messages and diffstats are semi-untrusted text interpolated into the LLM prompt; a crafted commit message could steer the summary. Acceptable for an internal dev tool and out of scope for a "first working prompt," but worth keeping in mind for the later "Quality feedback loop" phase. No change required here.

3. **`lang` is a free-form `str`.** `build`/`summarize` accept any string. Fine for the spike (dev branch = RU only). If validation is ever wanted, that belongs to the composition root / eval harness, not this feature — so no action now.

### Positive Notes

- Clean SRP split (`PromptBuilder` vs `Summarizer`) that keeps prompt churn isolated from service orchestration — exactly what makes the task-07 eval loop able to swap prompts without touching the service.
- Correctly resists premature wiring: no `OllamaClient`, no env reads, no `Settings` inside the feature.
- Task ordering and dependencies (Task 3 depends on Task 2) are accurate.
- Scope discipline: defers two-stage summarization and prompt-quality iteration to later phases instead of over-building now.

The plan is solid and implementable as written.

PLAN_REVIEW_PASS
