## Code Review — 8.1 Reasoner narrate

**Files reviewed (in full):** `src/reasoning/narration_prompt.py` (new), `src/reasoning/reasoner.py` (modified), `scripts/eval.py` (modified), `tests/reasoning/test_narrate.py` (new), against the spec `.ai-factory/specs/30-reasoner-narrate.md`, the plan, and the surrounding code (`src/episodic/linked_change.py`, `src/commits/models.py`, `src/reasoning/prompt.py`, `tests/reasoning/conftest.py`).

**Verification performed:**
- `uv run pytest tests/reasoning/test_narrate.py` → 4 passed; full `tests/reasoning/` suite → 18 passed (no regression in `answer`/cross-project tests).
- `uv run python -c "import scripts.eval; import src.reasoning.reasoner; import src.reasoning.narration_prompt"` → imports OK (composition-root wiring and new imports resolve).

**Risk level:** 🟢 Low

### Correctness assessment

The change is additive and matches the spec point-for-point:

- **Shared retrieval — no second mechanism.** `narrate` calls the same `_gather_context(query, change.repo)` helper `answer` uses; it does not re-implement retrieval/neighbor discovery and does not call `answer`. Guard satisfied.
- **Query from both sources.** `_narration_query` joins `change.completed_tasks` with every `commit.message` in `change.commits.commits`; neither is dropped when the other is empty (verified by the two query-construction tests). Correct.
- **Commits-as-floor / degradation.** `narrate` adds no try/except around `_gather_context`; it relies on that helper's existing per-store and per-neighbor isolation (reasoner.py:73–120). The store-failure test confirms a non-empty note still renders when both stores raise. `change.commits` always populates the prompt, so the note degrades to a commits-only digest rather than failing. Correct.
- **Narration prompt, not Q&A.** `NarrationPromptBuilder` is a distinct builder: completed tasks lead (with a commits-only digest fallback when `completed_tasks` is empty), commits are supporting detail, and the neighbor section is emitted only when `neighbor_chunks` is non-empty and is framed as what the change "unblocks". Prose-not-bullets and `in {lang}` are pinned in the instruction template. Matches the "owned details stay inside the owning class" rule and mirrors `ReasoningPromptBuilder`/`PromptBuilder`.
- **Eval handler.** `NarrateCaseHandler` resolves `{repo, range}` into a `LinkedChange` via `LinkedChangeResolver` and runs `narrate`; `_split_range` uses `rsplit("..", 1)` with a two-part guard (hardens against malformed ranges). The pool gate correctly widens to `("reasoner", "narrate")` and one `Reasoner` is shared across both handlers. `AiFactorySourceStrategy` is used for the resolver — correct, since `CodeSourceStrategy.roadmap_paths()` returns `()` and would starve task derivation.

No security surface (no new I/O, no user-controlled query paths beyond author-controlled eval data), no DB migration, and no new settings. Line lengths >100 in the changed files match the file's pre-existing style; there is no `line-length` config in `pyproject.toml` and no ruff installed, so this is not a lint regression.

### Deferred observations (non-blocking, out of scope for this task)

- **Test fixture realism vs. real `completed_tasks`.** `test_completed_tasks_are_included_in_the_retrieval_query` uses `"8.1 — Reasoner narrate"` as a completed task, but `LinkedChangeResolver` (`linked_change.py:16,83-89`) actually yields bare numeric identifiers (`"8.1"`) via `_TASK_ID_RE = \d+(?:\.\d+)+`. The code under test handles any string, so this is not a defect — but note that in production the task half of the retrieval query carries only bare IDs (weak embedding signal); the commit messages, always included, carry the real semantic weight. This is exactly what the spec specifies (`completed_tasks` = "done-marker identifiers"), so it is by-design, not a bug. [dismissed]
- **Eval linkage latent.** Per the plan-review's own deferred note, no `narrate` case is added to `evals/cases.yaml` and no reference note exists yet; the harness verification is latent until a user authors a `{repo, range, lang}` case and its reference. Correct per the "references user-authored (never fabricated)" rule. [routed → .ai-factory/specs/62-narrate-eval-case.md]

REVIEW_PASS
