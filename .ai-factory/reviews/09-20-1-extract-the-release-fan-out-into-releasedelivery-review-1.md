# Code Review: 20.1 — Extract the release fan-out into `ReleaseDelivery`

## Scope
Reviewed the code changes in:
- `src/delivery/service.py` (new `ReleaseDelivery` class)
- `src/ingestion/router.py` (fan-out removed, dispatch thinned)
- `src/main.py` (composition-root wiring)
- `tests/ingestion/test_release_delivery.py` → `tests/delivery/test_release_delivery.py` (suite retargeted)

Each file read in full. Ran the retargeted suite (12 passed), an import smoke test of `src.main` / `src.ingestion.router` / `src.delivery.service` (OK), and grepped the tree for any lingering `_deliver_release` references (none).

## Behavior-parity verification

The extraction preserves the original fan-out exactly:

- **Leg order** is byte-for-byte identical: `role_for_branch` → `mirror.ensure` → `versioner.next` → no-version early return → `resolve` → language union → optional `changelog.config` → `build_release_report` → `localizer.report_notes` → `github_release_client.create` → log line → `delivery_service.deliver` → optional `changelog.entry`.
- **Prerelease flag** is still `role is BranchRole.STAGING`; `_ENVIRONMENT_BY_ROLE[role]` mapping moved intact.
- **Graceful degradation** at both `config` and `entry` retains the same `try/except Exception` blocks with the same `logger.exception` messages and args.
- **Log lines** (`github release created…`, both `changelog…` exceptions, and the router's `release delivery skipped…`) are preserved character-for-character.
- **Isolation** is unchanged: the router still wraps the call in `_run_isolated("release_delivery", release_delivery.deliver, event)`; `release_delivery.deliver` is a bound `async def deliver(self, event)`, which matches `_run_isolated`'s `Callable[[PushEvent], Awaitable[None]]` signature.

### The two intentional deltas — both verified safe

1. **`app_available = bool(base_url)`** (was `changelog_client is not None and bool(base_url)`).
   Dropping the `changelog_client is not None` guard is correct: `changelog_client` is now a required constructor dependency, and the composition root builds `ReleaseDelivery` only inside the same `if` block that unconditionally assigns `app.state.changelog_client` (`src/main.py:115`). So whenever an instance exists, the client is non-`None`. No path reaches `None.config()`.

2. **`base_url = plan.changelog_base_url`** (was `getattr(plan, "changelog_base_url", None)`).
   Per the guard, and safe: `DeliveryPlan` (`src/routing/models.py:17`) declares `changelog_base_url: str | None = None`, so the attribute is always present on a real plan — the access can never raise `AttributeError`, and the removed fallback was unreachable.

## Presence-gate placement
The collaborator-presence gate is correctly split between the composition root (instance built only when all deps are wired) and the router (`getattr(app.state, "release_delivery", None)` → dispatch or log the skip). The class itself does no presence re-checks, matching the spec. The skip log line and its `(org_id, repo)` args are preserved.

## Router thinning
`src/ingestion/router.py` now contains only receive/verify/parse/dispatch. Removed imports (`functools`, `ChangelogEntry`) are confirmed unused elsewhere in the file; `role_for_branch`, `BranchRole`, and `_CREATION_BEFORE_SHA` are all still used and retained.

## Wiring / imports
`src/main.py:15` imports `DeliveryService, ReleaseDelivery`; the instance is constructed after all eight collaborators exist, with `delivery_plan_resolver` sourced from `app.state.delivery_plan_resolver` (set earlier at line 66, always present). No circular-import risk — `Report` and `PushEvent` are `TYPE_CHECKING`-only string annotations in `service.py`, and the import smoke test passed.

## Test suite
All 12 behavior cases retargeted at `ReleaseDelivery.deliver` with no case dropped, weakened, or merged. The `_collaborators` helper now returns the built instance plus a `Fakes` bundle; assertions are equivalent to the originals. Suite passes.

## Findings
None. The refactor is a faithful, behavior-preserving extraction; the two deliberate simplifications are both provably safe given the new constructor-injection contract.

REVIEW_PASS
