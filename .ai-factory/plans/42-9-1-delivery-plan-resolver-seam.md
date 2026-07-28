# Plan: 9.1 — Delivery-plan resolver seam

## Context
Add a `src/routing/` feature that turns a served push into a routing decision: classify a branch into a `BranchRole` in exactly one place, and resolve a repo/branch into an immutable `DeliveryPlan` behind a seam that later delivery tasks (9.3, reports, releases) consume. Ingestion stays role-agnostic — this is a pure seam, not wired into ingestion.

## Settings
- Testing: yes — one minimal contract test for the classification surface (see Task 5); it is a pure function whose only failure mode is wrong output without a crash, exactly the silent-failure surface the project's `test-philosophy` says to cover.
- Logging: minimal
- Docs: no

## Tasks

### Phase 1: Routing models

- [x] **Task 1: Add routing package and domain models**
  Files: `src/routing/__init__.py`, `src/routing/models.py`
  Create the new feature package. In `models.py` define:
  - `BranchRole(Enum)` with members `RELEASE`, `STAGING`, `DEV`.
  - `DeliveryPlan` as a frozen, `slots=True` dataclass (mirror the value-object style of `src/commits/models.py`) with fields `branch_role: BranchRole`, `is_release: bool`, `is_prerelease: bool`.
  Do NOT add the `telegram_channel`/`language` fields (added by 9.3) or the app `changelog_base_url` field (Phase 12) — they are deliberately out of scope here. Keep `DeliveryPlan` immutable.

### Phase 2: Classification and resolver

- [x] **Task 2: Branch-role classifier `role_for_branch`** (depends on Task 1)
  Files: `src/routing/resolver.py`
  Add module-level constants for the release and staging branch names (e.g. `RELEASE_BRANCHES = ("master", "main")`, `STAGING_BRANCH = "staging"`) and the single classification function `role_for_branch(branch: str) -> BranchRole`:
  - `master`/`main` → `BranchRole.RELEASE`
  - `staging` → `BranchRole.STAGING`
  - anything else → `BranchRole.DEV`
  Match is **exact** and case-sensitive against the constant names — `main-backup` and `staging2` fall to `DEV` (no prefix/substring matching). This is the ONLY place a branch string is compared to a role; no other code compares `branch == "master"` inline.

- [x] **Task 3: `DeliveryPlanResolver.resolve`** (depends on Task 2)
  Files: `src/routing/resolver.py`
  Add `class DeliveryPlanResolver` whose constructor takes an injected config abstraction (`Settings` from `src/core/config.py`) — stored for future config reads (channel/language land in 9.3); it must never read `os.getenv` or call `get_settings()` itself. Implement `resolve(self, org_id: int, repo: str, branch: str) -> DeliveryPlan`:
  - derive `branch_role` via `role_for_branch(branch)` (never re-compare branch strings here),
  - set `is_release = branch_role is BranchRole.RELEASE`,
  - set `is_prerelease = branch_role is BranchRole.STAGING`,
  - return the immutable `DeliveryPlan`.
  `org_id` and `repo` are part of the signature for the consumers built on this seam (config-scoped resolution in 9.3); they are accepted but not yet needed for role derivation.

### Phase 3: Composition-root wiring

- [x] **Task 4: Wire the resolver at the composition root** (depends on Task 3)
  Files: `src/main.py`
  Construct `DeliveryPlanResolver(settings)` in the `lifespan` startup (Settings is already read there as `settings`) and expose it on `app.state` (e.g. `app.state.delivery_plan_resolver`), following the existing `app.state.*` wiring pattern. Construct it **unconditionally** — alongside the always-run `served_repo_store`/`project_graph` wiring, **before** the `if settings.github_app_id is not None and …:` block. The resolver has no GitHub-App dependency and must always exist, since delivery (9.3) relies on it regardless of App config; it must NOT be placed inside the conditional block, where it would silently vanish when App settings are unset. This is a pure seam: do NOT call it from the ingestion router or any push-handling path — ingestion stays role-agnostic. The first real caller is the delivery service in 9.3.

### Phase 4: Test

- [x] **Task 5: Contract test for `role_for_branch`** (depends on Task 2)
  Files: `tests/routing/__init__.py`, `tests/routing/test_role_for_branch.py`
  Add a minimal unit test (mirroring the existing contract-test style under `tests/ingestion/`, `tests/graph/`, `tests/reasoning/`) pinning the classification cases from the spec's Verification section and the roadmap's `Verify:` line:
  - `main` → `BranchRole.RELEASE`, `master` → `RELEASE`,
  - `staging` → `BranchRole.STAGING`,
  - `feature/x` → `BranchRole.DEV`,
  - the exact/case-sensitive trap: `main-backup` → `DEV` and `staging2` → `DEV` (never a prefix/substring match).
  Optionally assert `DeliveryPlanResolver.resolve` derives the flags from the role (`RELEASE`→`is_release`, `STAGING`→`is_prerelease`, `DEV`→neither), which follows for free once `role_for_branch` is pinned. No LLM, DB, or GitHub dependency — pure functions, no fixtures needed.
