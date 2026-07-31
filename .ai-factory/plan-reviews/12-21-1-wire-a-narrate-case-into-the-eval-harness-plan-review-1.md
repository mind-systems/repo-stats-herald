## Plan Review Summary

**Files Reviewed:** 1 plan (targets `evals/cases.yaml`; verified against `scripts/eval.py`, `src/episodic/linked_change.py`, spec `62-narrate-eval-case.md`, existing `evals/reference/herald-narrate.md`, and git history)
**Risk Level:** 🟢 Low

### Context Gates
- **Architecture** (`.ai-factory/ARCHITECTURE.md`): PASS — the change adds only a data entry to a fixtures file; no module boundary or dependency rule is touched. The handler/runner it exercises are already wired at the composition root.
- **Rules** (`.ai-factory/RULES.md`): not present — skipped.
- **Roadmap:** Task recovers cleanly — plan heading "21.1 — Wire a `narrate` case into the eval harness" matches spec `.ai-factory/specs/62-narrate-eval-case.md` (Phase 21, "Ground truth for the eval harness"). Governing spec followed to leaf. No linkage gap.

### Verification performed
- **Range resolves to a genuine non-empty slice.** `git log 0783684..1bb7597` yields exactly 3 commits (`366e882` SinceDeployWindow, `e3972ec` release note as report, `1bb7597` GitHub release + version header). `0783684` is the parent of `366e882`, so the `before..after` git range in `LinkedChangeResolver.resolve` (linked_change.py:60) and its roadmap set-difference (before-ref `0783684` vs after-ref `1bb7597`) both capture the phase-11 window. The plan's parenthetical `(366e882..1bb7597)` describes the inclusive commit span; it is consistent with the literal `0783684..` range, not a contradiction.
- **Reference semantics match.** `evals/reference/herald-narrate.md` is a 9-line Russian narration describing exactly version + release note + delivery — the content of the pinned slice. `lang: ru` therefore pairs correctly with the reference's language.
- **Singular `lang` key is correct.** `NarrateCaseHandler.run` (scripts/eval.py:124-127) reads `inputs.get("lang", "ru")`; the plural `langs` key belongs only to `LocalizeCaseHandler` (eval.py:148). The plan's guard against copying the localize key shape is accurate.
- **Name pairing holds.** `EvalRunner.run` (eval.py:175) writes `evals/out/{case.name}.md` and pairs by name alone; `herald-narrate.md` already exists under `evals/reference/`, so `name: herald-narrate` avoids orphaning it. Any other name would break the pairing, as the plan states.
- **Dispatch is already wired.** `handlers["narrate"]` is constructed (eval.py:226-228) whenever any case has `type in ("reasoner", "narrate", "localize")` (eval.py:214); adding this case both triggers pool creation and is dispatched. No runner or handler edit needed — the plan's "do not edit handler/runner" instruction is correct.
- **YAML shape matches existing entries.** The proposed block-style entry with two-space list indentation matches the surrounding cases; `repo: "."` (quoted) is equivalent to the unquoted `repo: .` used elsewhere and parses identically.

### Critical Issues
None.

### Positive Notes
- The plan correctly identifies the singular-vs-plural `lang`/`langs` trap and pins it to the exact handler line — the most likely mistake here, pre-empted.
- The pinned literal commit range (rather than `HEAD~3..HEAD`) is the right call: it keeps the case input stationary under its fixed reference as new commits land, unlike the `summary`/`localize` cases whose references are regenerated. This reasoning is sound and matches the spec's intent.
- Scope is tightly fenced — one appended entry, nothing under `evals/reference/`, no code — matching the spec's guards exactly.

PLAN_REVIEW_PASS
