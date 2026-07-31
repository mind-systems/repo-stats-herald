## Plan Review Summary

**Plan:** 21.4 — Pin the eval cases to fixed commit ranges
**Files Reviewed:** 1 plan + `evals/cases.yaml`, `scripts/eval.py`, `src/commits/collector.py` (targets/consumers)
**Risk Level:** 🟢 Low

### Context Gates
- **Architecture** (`.ai-factory/ARCHITECTURE.md`): PASS — the change is confined to an eval fixture (`evals/cases.yaml`), a data file; no module boundary or dependency rule is touched.
- **Rules** (`.ai-factory/RULES.md`): PASS — no convention conflict; the comment discipline (no plan-layer references in code/tests) is respected, the added comment is about data drift, not the roadmap.
- **Roadmap**: WARN (non-blocking) — the plan heading is `21.4` and lives under `.ai-factory/plans/`, but the plan file carries no explicit `Spec:` linkage to a roadmap contract line. This mirrors the sibling `herald-narrate` pinning work already in the tree, so it is consistent with project practice; flagging only for traceability.

### Verified Facts (ground truth)
- Both pinned SHAs exist as commits (`git cat-file -t` → `commit`).
- `0783684..1bb7597` resolves to exactly **3** commits — identical to the current `HEAD~3..HEAD` window. The pinned window therefore preserves the input that produced the already-authored reference notes; outputs stay aligned.
- The three range-bearing cases named in the plan are exactly the ones with `range: HEAD~3..HEAD`: `herald-recent` (summary, `lang: ru`), `herald-recent-en` (summary, `lang: en`), `herald-localize` (localize, `langs: [en, ru]`). No case is missed or misnamed.
- `herald-narrate` is a genuine precedent: same `repo`, same fixed range, with the exact drift-explaining comment the plan says to mirror (`cases.yaml:51-59`).
- Name-based reference pairing is confirmed: `EvalRunner.run` writes `out/<case.name>.md` (`scripts/eval.py:175`) and `evals/reference/` holds one file per case name — so leaving names unchanged is correctly identified as the guard that keeps output/reference filenames stable.
- Both consuming code paths accept the fixed-hash form. `SummaryCaseHandler` passes the raw range string to `GitCommitCollector.collect`, which runs `git log <hash>..<hash>` after `--end-of-options` (`collector.py:347-366`) — valid revision syntax. `LocalizeCaseHandler._split_range` does `rsplit("..", 1)` (`scripts/eval.py:151-155`), which splits `hash..hash` cleanly. No parsing risk from full SHAs.
- The two rangeless cases `mind-features` and `herald-self-query` carry no `range` field and are correctly declared out of scope.

### Critical Issues
None.

### Minor Observations (non-blocking)
- The plan says "Add a short comment above the pinned cases" (singular block), but the three cases are non-contiguous: `herald-recent`/`herald-recent-en` sit together (lines 2-12) while `herald-localize` sits lower (lines 45-49) and already has an explanatory comment about the pivot. The implementer should place the drift-explaining comment above each cluster (and augment rather than replace `herald-localize`'s existing comment). The plan's intent is clear enough that this is a placement detail, not a gap.

### Positive Notes
- The plan correctly anchors on ground truth: it mirrors an existing pinned case rather than inventing a convention, and the drift-prevention comment it mandates is a real safeguard against a future "modernize back to HEAD" edit.
- Scope is tight and explicit — the guards list (names unchanged, rangeless cases untouched, no reference authored) matches exactly what the codebase requires for the references to keep pairing.
- Choosing SHAs that reproduce today's `HEAD~3..HEAD` window is the right call: it decouples the input from history growth without invalidating the existing reference notes.

PLAN_REVIEW_PASS
