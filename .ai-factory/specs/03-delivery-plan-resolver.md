# 9.1 — Delivery-plan resolver seam

**Phase:** 9 — Delivery & routing. Depends on 2.1 (a parsed push) and 2.2 (gated to a served org), which give it the org/repo/branch to resolve. First task of delivery; a served push becomes a routing decision the delivery tasks consume.

## Current state

After 2.1–2.2, a served push exists as a `PushEvent`, but nothing turns it into a routing decision. There is no notion of a branch role or a delivery plan. `docs/spec/delivery.md` describes the branch role and the delivery plan; `docs/spec/configuration.md` describes the resolver seam.

## Change

Add a routing feature that resolves a push into a delivery plan, with branch-role classification in one place, behind a seam so its backing store can change later.

- `src/routing/models.py`:
  - `BranchRole` (`Enum`: `RELEASE`, `STAGING`, `DEV`).
  - `DeliveryPlan` (`branch_role: BranchRole`, `is_release: bool`, `is_prerelease: bool`; the channel field is added by 9.3, the app field (`changelog_base_url`) by Phase 12 — out of scope here).
- `src/routing/resolver.py`:
  - `role_for_branch(branch: str) -> BranchRole` — the single classification function: `master`/`main` → `RELEASE`, `staging` → `STAGING`, else `DEV`. The release/staging branch names are module-level constants; the comparison lives only here.
  - `DeliveryPlanResolver.resolve(org_id: int, repo: str, branch: str) -> DeliveryPlan` — sets `branch_role` and the `is_release`/`is_prerelease` flags derived from it (release → is_release, staging → is_prerelease). Reads any config it needs through an injected `Settings`/config abstraction, not env.
- Constructed at the composition root and injected into the delivery path — this is a pure seam, **not** wired into ingestion. Under the current model ingestion is role-agnostic (it drives the event stream → memories regardless of branch); the plan this resolver produces is consumed by the delivery service (9.3) and the paths built on it — the reports (Phase 10) and the release milestones (Phase 11), which are where the branch role actually gates behaviour.

## Files & types

- new `src/routing/__init__.py`, `src/routing/models.py`, `src/routing/resolver.py`
- constructed at the composition root (`main.py`) and injected into the delivery path, per the DI discipline

## Guards

- Branch-role compared in **one place** (`role_for_branch`); never `branch == "master"` inline elsewhere.
- Release/staging branch names as constants — a future differently-named release branch is handled by extending this function only.
- Resolver depends on an injected config abstraction, not `os.getenv`.
- `DeliveryPlan` immutable; the channel field deliberately absent until 9.3, the app field (`changelog_base_url`) until Phase 12.

## Verification

- `resolve(org_id, "o/r", "main")` → `plan.branch_role == RELEASE`, `is_release=True`.
- `resolve(org_id, "o/r", "staging")` → `STAGING`, `is_prerelease=True`.
- `resolve(org_id, "o/r", "feature/x")` → `DEV`, no release flags.
