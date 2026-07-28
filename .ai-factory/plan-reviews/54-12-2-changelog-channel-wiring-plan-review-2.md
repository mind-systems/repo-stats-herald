## Code Review Summary

**Files Reviewed:** 1 plan (`54-12-2-changelog-channel-wiring.md`) against `src/ingestion/router.py`, `src/main.py`, `src/delivery/changelog_client.py`, `src/reasoning/localizer.py`, `tests/ingestion/test_release_delivery.py`, spec `.ai-factory/specs/23-changelog-channel-wiring.md`, and `.ai-factory/specs/22-changelog-protocol-client.md`.
**Risk Level:** 🟢 Low

This is the second-round review. Plan v2 resolves both findings raised in plan-review-1 and the minor nit. The plan is well-grounded and ready to implement.

### Context Gates
- **Architecture (WARN):** `_deliver_release` remains a growing module-level orchestration inside the ingestion router, in tension with ARCHITECTURE.md's "routers are thin, services own business logic" guidance. This is a **pre-existing** condition introduced by 11.3; the plan's inline placement (Deviation #1) is the correct local choice for 12.2 and correctly avoids splitting the changelog protocol across two modules. Structural extraction is a phase-level decision, not this task's — carried below as a deferred observation.
- **Rules:** `.ai-factory/RULES.md` is intentionally empty (documented as the correct result, no counter-defaults) — nothing to violate.
- **Roadmap / Spec:** Plan heading matches ROADMAP line 12.2 and spec 23. Every guard in spec 23 is honored: one-place `role→environment` map (`_ENVIRONMENT_BY_ROLE`, spec lines 14/27), zero re-derivation (spec 33/41 — reuses `role`/`version`/`github_url`/`notes`/single `declared_languages`), last-leg-after-Telegram ordering (spec 15), individually caught+logged failure (spec 15), unmapped-repo skip (spec 26), and declared-languages-only `summaries` (spec 37). Task 1's composition-root registration follows the "wire concretes only at the composition root" pattern and is correctly co-located with the other release-delivery collaborators.

### Verification of the three ground-truth deviations
All three deviations re-checked against current code and confirmed accurate:
- **Deviation #1** — the fan-out lives in `router.py::_deliver_release` (line 32), not `delivery/service.py`. Confirmed: the function holds every local `entry` needs (`role` line 55, `version` line 61, `base_url` line 70, `app_available` line 71, `github_url` line 83, `notes` line 81) and carries the extension-point comment at `router.py:93-95`. Spec 23's `service.py` Files hint (line 21) is legitimately overridden by ground truth — conformance, not drift.
- **Deviation #2** — `app.state.changelog_client` is threaded into the partial via `getattr(state, "changelog_client", None)` at `router.py:192` but is never set in `main.py` (confirmed absent from the lifespan block, lines 100-116), so the channel is dormant. Fix in Task 1 is necessary.
- **Deviation #3** — `ChangelogClient.config` returns `list[str]` (`changelog_client.py:27`, `return response.json()["languages"]`), so `router.py:75`'s `set(config.languages)` would `AttributeError`, be swallowed by the `except` (line 76), and force `app_available=False`. The test fake (`FakeChangelogConfig`, lines 114-129) masks it. The fix (consume as `list[str]`, align the fake) is correct and necessary for the channel to fire at all.

### Critical Issues
None.

### Issues
None. Both prior-round findings are resolved:
- The **stale docstring** (`router.py:44-54`, second paragraph "dormant until the changelog app itself is wired") now has an explicit rewrite step in Task 3 (plan lines 71-72), preserving the still-true degrade-to-fixed-channel behavior.
- The **`None`-value coercion** is fixed: the payload now uses `summaries={lang: notes[lang] or "" for lang in declared_languages}` (plan line 54), mirroring the sibling channels' `... or ""` at `router.py:88` and `router.py:97`. This correctly avoids posting `null` when `PivotLocalizer.report_notes` maps every language to `None` on an empty report (`localizer.py:84-85`). This intentionally strengthens spec 23 line 14's raw `notes[lang]` shape, which is a conscious, well-justified improvement, not a divergence.

### Verified correctness points
- **No `KeyError` on `notes[lang]`:** `union |= set(declared_languages)` (Task 2) guarantees `report_notes` (keys == `langs`) covers every declared language, so `notes[lang]` for `lang in declared_languages` always resolves.
- **No `KeyError` on `_ENVIRONMENT_BY_ROLE[role]`:** the release-delivery task is only scheduled when `role in (BranchRole.STAGING, BranchRole.RELEASE)` (`router.py:178`), and `role` is recomputed inside `_deliver_release` from the same `event.branch` (line 55) — so the lookup key is always present.
- **`app_available` gating is sound:** it is `True` only when `changelog_client is not None and bool(base_url)` and `config` succeeded (`router.py:71-78`). An unmapped repo (`base_url` `None`) or an unreachable app never reaches `entry`. Registering `changelog_client` in `main.py` does not affect the `all(... is not None)` collaborator check (it is threaded separately at line 192), so the channel activates independently and a missing client stays a no-op.
- **Import correctness:** `from src.delivery.changelog_client import ChangelogClient` / `ChangelogEntry` are the correct symbols/path; `BranchRole` is already imported at `router.py:15` and the plan explicitly says not to re-add it (line 41) — the prior duplicate-import nit is resolved.

### Positive Notes
- Deviation #3 (the `config.languages` latent bug that the green test actively concealed) remains a genuinely valuable catch; fixing the client-shaped fake alongside it is the right call.
- The zero-re-derivation guard is honored concretely and backed by an explicit test asserting `config`/`report_notes` call counts (Task 4).
- `_ENVIRONMENT_BY_ROLE` as a module-level constant cleanly satisfies spec 23's "one place" mapping guard.
- The Task 4 test matrix mirrors spec 23's verification matrix exactly (mapped-reachable staging, release→production, unmapped skip, unreachable-at-`entry`, zero-re-derivation, None-version).

## Deferred observations
- Affects: Phase 11 / 12 (`src/ingestion/router.py::_deliver_release`) — the release fan-out is a growing module-level orchestration living in the ingestion router, in tension with ARCHITECTURE.md's "routers are thin, services own business logic" guidance. This originates in 11.3 and is out of 12.2's scope; whether to extract it into a delivery-side service (as spec 23's original `service.py` hint envisioned) is a structural decision for the phase, not this task. The plan's inline placement is the correct local choice given the current shape. [routed → .ai-factory/specs/60-release-delivery-extraction.md]

PLAN_REVIEW_PASS
