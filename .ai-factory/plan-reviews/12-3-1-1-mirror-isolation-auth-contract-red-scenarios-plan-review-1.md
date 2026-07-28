## Plan Review Summary

**Plan:** 3.1.1 — Mirror isolation & auth contract (red scenarios)
**Files Reviewed:** plan + governing specs (`41`, `04`), `ARCHITECTURE.md`, `RULES.md`, ingestion models, existing test scaffolding (`tests/conftest.py`, `tests/ingestion/test_webhook_contract.py`), `src/commits/collector.py`
**Risk Level:** 🟡 Medium

### Context Gates
- **Architecture (`.ai-factory/ARCHITECTURE.md`):** ✅ Aligned. File paths (`src/github/{__init__,app_auth,mirror}.py`) follow the feature-modular layout. DI-via-constructor is honored — stubs take primitives (`app_id`, `private_key`, `mirror_root`, `clone_source`) and are wired at the composition root in 3.1.2. `RepoMirror` depending on the concrete `GitHubAppAuth` (rather than an ABC) is correct here: both live in one feature and no second auth implementation is imminent, so introducing an abstraction would violate principle 4 ("introduce an ABC when a real second implementation is imminent — not speculatively"). The `clone_source` seam is a plain `Callable`, explicitly *not* a named abstraction, so it adds no interface-marker surface — consistent with the global naming rule.
- **Rules (`.ai-factory/RULES.md`):** ✅ Empty by design; nothing to enforce.
- **Roadmap (`.ai-factory/ROADMAP.md`):** ✅ Linked. The plan maps to the `[ ] 3.1.1` contract line; the line and spec `41` were both updated in this working tree to add the single-flight *discrimination* requirement, and the plan's Task 7 implements exactly that. Spec chain walked: contract line → spec `41` (governing, this task) → spec `04` (the behavior `ensure`/`tree`/`token` are pinned against). All consistent.
- **Skill-context (`aif-review/SKILL.md`):** absent — no project overrides to apply.

### Critical Issues
None. The stub surface, types (`AbstractContextManager[Path]`, `token(org_id)->str`, `ensure`/`tree`), repo/org identity (matches `PushEvent.repo: str` + `org_id: int` in `src/ingestion/models.py`), the "no `Settings` change here" boundary, and the single-flight test design all check out. No migration is in scope (no DB touched by this task). The guard reinterpretation ("no git subprocess" governs *production* code, test scaffolding may build a real git repo) is defensible: `GitCommitCollector` already makes git a hard project dependency, so a git-building fixture is consistent with the existing test environment.

### Important Issues

1. **`local_upstream` git fixture is under-specified for determinism — risks a *fixture error*, which the spec explicitly forbids (Task 4, `tests/github/conftest.py`).**
   Spec `41` Verification requires the red suite to fail "only because there's no logic yet — no import errors, **no fixture errors**." This fixture would be the first in the repo to build a git repo (grep confirms no existing test does), so it cannot lean on ambient developer config. Two concrete traps the plan leaves open:
   - **Committer identity.** A bare `git commit` fails (`Author identity unknown`) on any environment without global `user.name`/`user.email` (fresh CI, container). That surfaces as a *fixture error*, not a logic-absence red — exactly what the verification criterion prohibits. The plan should pin that the fixture supplies identity explicitly, e.g. `git -c user.name=... -c user.email=...` per commit (or `GIT_AUTHOR_*/GIT_COMMITTER_*` env), rather than relying on global config.
   - **Branch creation.** The plan says "two branches (e.g. `main` and `feature`)." This is *mitigated* because the fixture "yields the two ref names" (so the default-branch name — `main` vs `master` across git versions/`init.defaultBranch` — doesn't leak into assertions), but the plan should make the mitigation explicit: create both branches deterministically (`git checkout -b <name>`) and drive the tests off the yielded names, never a hardcoded `"main"`.
   These are within this task's file boundary (the conftest is authored here), so they are findings, not deferrable. Recommend adding a one-line determinism note to Task 4's Assumptions.

### Minor Issues

2. **`counting_mint` signature when patched onto an instance (Task 7, `test_app_auth_single_flight.py`).**
   `monkeypatch.setattr(auth, "_mint_token", counting_mint)` installs an *instance attribute*. A plain function stored on the instance is not bound, so 3.1.2's `self._mint_token(org_id)` will call `counting_mint(org_id)` **without** `self`. The helper must therefore be defined as `def counting_mint(org_id)` (or a closure), not `def counting_mint(self, org_id)`. This never fires against the 3.1.1 stub (whose `token()` raises before reaching `_mint_token`), so it won't cause a wrong-reason red now — but the helper is authored in this task and would silently break 3.1.2's green run. Worth a one-line note so the implementer gets the arity right.

### Positive Notes
- **Single-flight discrimination is handled with real rigor.** Task 7 directly implements the spec's hard requirement: an N-party `threading.Barrier` *in test code* (correctly reasoned as fatal if placed inside the mint), plus a blocking `counting_mint` to widen the in-flight window so a naive per-request mint yields `mint_count == N` and fails. The plan even reasons through why the stub keeps `mint_count == 0`. This is precisely the "reliably fails a naive impl, not merely passes a correct one" gate.
- **`ensure()` vs `tree()` separation is grounded in spec `04`.** The plan correctly has tests call `ensure()` once before opening any `tree()` context (matching `04`'s clone-once/fetch-later store, with `tree()` never auto-`ensure`-ing), so the same tests green unchanged in 3.1.2.
- **Both 3.1.2 override seams (`clone_source`, `_mint_token`) are pinned now with explicit rationale**, giving the offline tests a real clone source and a real patch target — the "green unchanged in 3.1.2" promise is concretely supported rather than asserted.
- **Constructors are provably side-effect-free** (store-only, PEM *content* not a path, no FS touch), so "constructing must not raise" holds and fixtures resolve cleanly.

## Deferred observations
- Affects: 3.1.2 / spec `.ai-factory/specs/04-repo-mirror.md` — This plan imposes a naming contract on 3.1.2 (the single mint step must be the method `_mint_token`, since Task 7's test binds a counting patch to that exact attribute), but spec `04` does not mention `_mint_token`. The red test is the de-facto enforcement, which is acceptable TDD; still, when 3.1.2 is implemented, `04` should record that `token()` delegates its one mint to `_mint_token` so the private-name coupling is a documented contract rather than an implicit test dependency. Outside this task's file boundary (spec `04` is 3.1.2's spec), hence deferred. [dismissed]
