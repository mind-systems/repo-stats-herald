## Plan Review Summary

**Plan:** 22.1 — Take the foreign product name out of the concept docs
**Files Reviewed:** 1 plan, against 2 target docs + governing spec + roadmap line
**Risk Level:** 🟢 Low

### Context Gates
- **Roadmap** (`.ai-factory/ROADMAP.md`, Phase 22, line 13): PASS — the plan maps cleanly to the `[ ] 22.1` contract line and its `Spec:` tag. The contract's guards (keep each argument whole, anonymise rather than delete or swap for the contrasted product, move the derivation example to the org's own product, edit nothing under `plans/`/`plan-reviews/`/`reviews/`/`handoffs/` and no completed spec or `[x]` line) are all reflected in the plan.
- **Governing spec** (`.ai-factory/specs/68-foreign-product-name-sweep.md`): PASS — the plan's two tasks correspond one-to-one with the spec's "Change" and "Files & types" sections, and the plan's guard ("do not replace the second product with `mind`") restates the spec's tautology guard.
- **Architecture** (`.ai-factory/ARCHITECTURE.md`): N/A — docs-only change, no module boundary or dependency-rule surface touched.
- **Rules** (`.ai-factory/RULES.md`): PASS — file is intentionally empty; no project counter-default applies.
- **Skill-context** (`.ai-factory/skill-context/aif-review/SKILL.md`): absent — no project-specific overrides to apply.

### Critical Issues
None.

### Verification against ground truth
- **Mention count is correct.** A repo-wide `grep` for `tradeoxy` returns exactly four live mentions, all inside the two named docs: `product-scope.md:16` (`tradeoxy_core`), `:17` (`tradeoxy_broker`), `:91` (`tradeoxy`), and `derivation-modes.md:15` (`tradeoxy_broker`). The plan's Task 1 covers the first three, Task 2 the fourth. No live mention is left unaddressed.
- **Every quoted anchor matches the file verbatim.** The "Why" two-products sentence (lines 14–17), the consequence clause "would blend a trading change into a health project's context" (line 19), the membership/dependency line "Two separate products (`mind`, `tradeoxy`) can share such an edge without being one product." (lines 91–92), and the derivation sentence "Every ai-factory repo predates its own `.ai-factory/`; `tradeoxy_broker` grew its docs gradually." (lines 15–16) all read exactly as the plan cites them, so each edit will anchor.
- **File paths and section titles are correct.** `docs/concepts/product-scope.md` and `docs/concepts/derivation-modes.md` both exist; the section headings the plan names ("Why", "Membership and dependency are two relations") match the actual headings.
- **`mind_api` is a sound replacement.** It already appears in `product-scope.md` as one of the health platform's repositories, so reusing it in `derivation-modes.md` keeps the illustration coherent with the org's own product and satisfies the spec's "move the example to a repository of this organization's own product."
- **Scope decision on `mind-systems`/`mind` is deliberate, not an omission.** Lines 36 and 114 keep `mind-systems` (the organization) and `mind`/`mind_*` (the org's own product) named. The plan (Task 1, "Leave every `mind`/`mind_*` mention untouched") and the spec both treat the foreign product as `tradeoxy` alone, so retaining these is by design — the roadmap phase title targets the foreign product, and the argument still needs the organization named.
- **Arguments survive the anonymisation.** After the edits the "Why" section still rests on two unrelated products under one organization (health `mind` + unnamed unrelated platform), the consequence claim about org-wide retrieval still stands (Task 1 bullet 2 rewords it to the unnamed product), and the membership/dependency passage still shows two products sharing an edge (unnamed pair) — matching the spec's three Verification points.

### Positive Notes
- The plan carries the tautology guard explicitly into Task 1 ("do not replace the second product with `mind`"), which is the single subtlest failure mode of this task; an implementer reading only the task bullets cannot miss it.
- Each edit bullet quotes the exact current text and states the required post-condition, so the edits are unambiguous and self-verifying without re-deriving intent.
- Scope is tightly bounded to the two files with no incidental churn, honoring the "no history is edited" guard by construction.

PLAN_REVIEW_PASS
