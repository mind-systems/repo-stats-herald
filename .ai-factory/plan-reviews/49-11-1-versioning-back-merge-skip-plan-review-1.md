## Plan Review Summary

**Plan:** `.ai-factory/plans/49-11-1-versioning-back-merge-skip.md`
**Governing spec:** `.ai-factory/specs/19-versioning.md` → `docs/behavior/delivery.md#versioning`
**Roadmap task:** `ROADMAP.md` 11.1 — Versioning + back-merge skip
**Risk Level:** 🟢 Low

### Context Gates
- **Architecture (`.ai-factory/ARCHITECTURE.md`):** ALIGNED. `Versioner` receives `RepoMirror`, `GitCommitCollector`, and a primitive `version_increment` through the constructor and never builds a concrete client — matching the dependency rule and the existing precedent (`src/episodic/backfill.py`, `src/knowledge/sync.py` both inject `RepoMirror`; `backfill` also injects `GitCommitCollector`). Importing the `BranchRole` enum from `src/routing/models.py` is a public value-object type import, not a reach into another feature's `service.py`, and mirrors how `DeliveryPlan` already consumes `BranchRole`. No boundary violation.
- **Rules (`.ai-factory/RULES.md`):** N/A — file is intentionally empty (no counter-defaults recorded for this project).
- **Skill-context (`.ai-factory/skill-context/aif-review/SKILL.md`):** absent — no project-specific review overrides to apply.
- **Roadmap linkage:** PRESENT. The plan matches the 11.1 contract line and spec verbatim on the shared-primitive set, the `next(...)` signature, the no-tag/staging/promotion/hotfix/back-merge behaviors, and the preserved-history precondition.

### Critical Issues
None.

### Verified Strengths
The plan is faithful to the spec and grounded in the actual code. Concretely verified:

- **`new_commits` command shape is correct.** I ran the prescribed invocation (`git rev-list <before>..<after> --no-merges --not --end-of-options <exclude_ref>`) against a throwaway repo covering (a) a staging-unique non-merge commit and (b) a `--no-ff` merge-commit back-merge of the default branch into staging with no unique work. Case (a) returned the introduced SHA; case (b) returned empty with exit 0. The `--not` toggle survives across `--end-of-options` and correctly negates `exclude_ref`, so both fast-forward and merge-commit back-merges read as empty. This is the plan's crux silent-failure surface and it holds.
- **API surface exists as referenced.** `RepoMirror.object_store_path(repo) -> Path` (mirror.py:56) and `RepoMirror.default_branch(repo) -> str` (mirror.py:71) are present and are the only two mirror methods `Versioner` needs — matching the plan's fake-mirror stub in Task 6. `BranchRole` (routing/models.py:5) has exactly the `RELEASE`/`STAGING`/`DEV` members the plan gates on.
- **Collector idiom is accurately described.** The three new primitives follow the established `-C <repo_path>` / `--end-of-options` / `subprocess.run(check=False)` / `splitlines()`-drop-blank pattern already used by `first_parent_steps`, `changed_paths`, `_rev_list`. `git tag` and `git merge-base --is-ancestor` both work against the bare `--mirror` store.
- **Config change is precise.** `src/core/config.py` currently imports `from typing import Annotated`; adding `Literal` and a `Literal["major","minor","patch"] = "patch"` field is correct, and pydantic-settings does raise a startup `ValidationError` on an out-of-set value — no custom validator needed, as claimed.
- **`Version` file placement conforms to the spec.** Housing both `Version` and `Versioner` in `versioner.py` deviates from the usual `models.py`/`service.py` split, but the governing spec's "Files & types" section explicitly dictates this exact layout — conformance, not a defect.
- **Totality of `next` is handled deliberately.** The RELEASE "First version" fallback (no reachable `-rc` candidate and no full release → `v0.1.0`) is a sound, explicitly-flagged extension that keeps `next` total for the case the spec leaves implicit (only-`-rc`-tags-none-reachable), and it stays consistent with the no-tag rule rather than bumping a synthetic `v0.0.0`. Semver-max including both full and `-rc` bases, with full-above-`-rc` at equal base rank, correctly yields `v1.2.1-rc → v1.2.2-rc` on successive pushes and `v1.10.0 > v1.9.0`.
- **Test plan pins the right surface.** Task 5 exercises `new_commits` directly (fast-forward back-merge, merge-commit back-merge, genuine new work) rather than only via `Versioner`, satisfying the spec's "pin the check specifically" mandate; Task 6 covers every entry in the spec's Verification list including the hotfix round-trip red case.

## Deferred observations
- Affects: `.ai-factory/specs/` task 11.3 (the push-event → `Versioner.next` wiring) — The STAGING back-merge guard runs `new_commits(bare, before, after, exclude_ref)` first and treats an empty result (including a non-zero `git` exit) as a back-merge → `None`. On a branch-creation push GitHub sends `before` as the all-zero SHA (`0000…0000`); `git rev-list 000..after` exits non-zero, yields an empty tuple, and the first-ever `staging` push would be silently skipped as a back-merge instead of cutting `v0.1.0-rc`. This is outside 11.1's file boundary — `next` is specified over resolved `before`/`after` SHAs and the plan's own tests drive explicit commits — but 11.3 must resolve a null/creation `before` (e.g. to the empty-tree SHA or the branch's fork point) before calling `next`, or the first staging release is lost. Worth pinning as an input precondition on `next` when 11.3 is decomposed. [routed → .ai-factory/specs/53-creation-sha-normalization.md] [routed → .ai-factory/specs/54-git-failure-vs-empty-range.md]

PLAN_REVIEW_PASS
