## Plan Review Summary

**Plan:** 3.1.1 — Mirror isolation & auth contract (red scenarios)
**Files Reviewed:** plan + governing spec `41`, target spec `04`, `ARCHITECTURE.md`, `RULES.md`, `ROADMAP.md`, ingestion models (`src/ingestion/models.py`), existing test scaffolding (`tests/conftest.py`, `tests/ingestion/test_webhook_contract.py`), prior plan-review-1
**Risk Level:** 🟢 Low

This is the second review. Review-1's two findings and its deferred observation were the only open items; both findings are now closed in the plan text. Re-verified the whole surface against ground truth.

### Context Gates
- **Architecture (`.ai-factory/ARCHITECTURE.md`):** ✅ Aligned. File paths (`src/github/{__init__,app_auth,mirror}.py`) follow the feature-modular layout. Constructors take primitives (`app_id`, `private_key`, `mirror_root`, `clone_source`) and are wired at the composition root in 3.1.2 (principle 3/5). `RepoMirror` depending on the concrete `GitHubAppAuth` is correct — same feature, no second auth impl imminent (principle 4 forbids the speculative ABC). `clone_source` is a plain `Callable`, explicitly not a named abstraction, so it adds no interface-marker surface.
- **Rules (`.ai-factory/RULES.md`):** ✅ Empty by design; nothing to enforce.
- **Roadmap (`.ai-factory/ROADMAP.md`):** ✅ Linked. Plan maps to the `[ ] 3.1.1` contract line; spec chain walked contract line → spec `41` (governing) → spec `04` (the behavior the stub surface is pinned against). The contract line's single-flight *discrimination* requirement is implemented by Task 7. Consistent throughout.
- **Skill-context (`aif-review/SKILL.md`):** absent — no project overrides to apply.

### Review-1 Follow-up (both findings closed)
1. **Fixture determinism (was Important).** Task 4 now pins committer identity explicitly (`git -c user.name=herald-test -c user.email=herald@test.invalid commit …` or `GIT_AUTHOR_*/GIT_COMMITTER_*`), `git init -q`, a pinned branch name so `init.defaultBranch` can't leak, deterministic branch creation (`git checkout -b <name>`), and yielding the ref names for tests to drive off — never a hardcoded `main`/`master`. This directly satisfies spec `41`'s "no fixture errors" verification criterion on a fresh CI/container. ✅ Resolved.
2. **`counting_mint` arity (was Minor).** Task 7 now spells out that `monkeypatch.setattr(auth, "_mint_token", …)` installs an unbound instance attribute, so the helper must be `def counting_mint(org_id)` (not `(self, org_id)`) to keep 3.1.2's `self._mint_token(org_id)` green. ✅ Resolved.

### Critical Issues
None. The stub surface (`GitHubAppAuth.token`/`_mint_token`, `RepoMirror.ensure`/`tree`), the types (`AbstractContextManager[Path]` from `contextlib`, `Callable` from `collections.abc`, `Path` from `pathlib`), the `(repo: str, org_id: int)` identity matching `PushEvent`, the "no `Settings` change here" boundary (Settings fields belong to 3.1.2 per spec `04`), and the side-effect-free store-only constructors all check out against the specs and the codebase. No migration is in scope — this task touches no database. The `mirror_root: Path` constructor param reconciles cleanly with spec `04`'s `mirror_root: str` Settings field at the 3.1.2 composition root.

Single-flight test design (Task 7) satisfies spec `41`'s discrimination gate: an N-party `threading.Barrier` in *test* code (correctly reasoned fatal if placed inside the mint), a blocking `counting_mint` widening the in-flight window so a naive per-request mint yields `mint_count == N` and fails while a correct single-flight yields `1`. Verified no deadlock in either run: in the stub run all N threads clear the barrier and each raises `NotImplementedError` from `token()` before `_mint_token` is ever reached (`mint_count` stays 0, red for the right reason); in the 3.1.2 green run all N clear the barrier, one acquires the single-flight lock and mints once, the rest block on the lock.

### Positive Notes
- **Green-unchanged-in-3.1.2 promise is concretely supported, not asserted.** Both override seams are pinned now with rationale: `clone_source` gives the isolation/cleanup tests a real offline clone source (local upstream) that 3.1.2 keeps, and the private `_mint_token` gives Task 7 a real patch target that binds without `raising=False`.
- **`ensure()` vs `tree()` separation is grounded in spec `04`.** Tests call `ensure()` once before opening any `tree()` context, matching `04`'s clone-once/fetch-later store with `tree()` never auto-`ensure`-ing — so the same tests green unchanged.
- **Red-for-the-right-reason is preserved throughout.** Every red test fails on logic absence (`NotImplementedError`) with fixtures/patch/barrier binding cleanly first — matching the discipline already established in `tests/ingestion/test_webhook_contract.py`.
- **Constructors are provably side-effect-free** (store-only, PEM *content* not a path, no FS touch), so "constructing must not raise" holds and fixtures resolve cleanly.

## Deferred observations
- Affects: 3.1.2 / spec `.ai-factory/specs/04-repo-mirror.md` — This plan imposes a naming contract on 3.1.2 (the single mint step must be the method `_mint_token`, since Task 7 binds a counting patch to that exact attribute), but spec `04` does not mention `_mint_token`. The red test is the de-facto enforcement, which is acceptable TDD; still, when 3.1.2 is implemented, spec `04` should record that `token()` delegates its one mint to `_mint_token` so the private-name coupling becomes a documented contract rather than an implicit test dependency. Outside this task's file boundary (spec `04` is 3.1.2's spec), hence deferred. [dismissed]

PLAN_REVIEW_PASS
