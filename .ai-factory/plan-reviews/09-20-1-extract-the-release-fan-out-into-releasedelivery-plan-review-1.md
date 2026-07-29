## Plan Review Summary

**Plan:** 20.1 — Extract the release fan-out into `ReleaseDelivery`
**Files the plan touches:** `src/delivery/service.py`, `src/main.py`, `src/ingestion/router.py`, `tests/ingestion/test_release_delivery.py` → `tests/delivery/test_release_delivery.py`
**Risk Level:** 🟢 Low — a pure, well-scoped refactor with an existing 12-case suite as the behavior oracle.

### Context Gates

- **Architecture (`.ai-factory/ARCHITECTURE.md`):** PASS. The plan removes a genuine, roadmap-acknowledged anti-pattern ("logic in entry points" — ~85 lines of fan-out inside the webhook router) and relocates it behind a constructor-DI service wired at the composition root. Verified the new cross-feature edges are safe: `grep` for `src.delivery` across `src/` shows **no** feature imports `delivery` (only `main.py` and the router), so adding runtime imports of `reasoning.localizer` / `versioning.versioner` / `github.mirror` / `routing.resolver` into `delivery/service.py` introduces **no import cycle**. `delivery → changelog` (`Report`) and `delivery → ingestion` (`PushEvent`) are correctly held type-only under a `TYPE_CHECKING` guard with string annotations, mirroring the established pattern in `src/changelog/release.py`. `delivery → routing` already exists (`DeliveryService` imports `DeliveryPlan`), and `ChangelogEntry` is same-feature (`src/delivery/changelog_client.py`), so no new runtime feature coupling is added beyond what DI justifies.
- **Rules (`.ai-factory/RULES.md`):** PASS (file is intentionally empty; no counter-defaults declared).
- **Roadmap (`.ai-factory/ROADMAP.md` line 36) + governing spec (`.ai-factory/specs/60-release-delivery-extraction.md`):** PASS. Every spec guard is reflected in the plan — same legs/order, identical graceful degradation in all three changelog cases, unchanged isolation wrapper, log lines preserved verbatim, base URL read as a plain attribute, the presence gate kept at the composition root and router, and all twelve behavior cases retargeted (none dropped/weakened/merged). The plan is a faithful decomposition of the spec.

### Critical Issues

None. The plan is implementable as written. Verification performed:

- **Line references are accurate.** `_deliver_release` is router lines 47–129, `_ENVIRONMENT_BY_ROLE` is line 23, and the collaborator-dict gate is lines 212–233 — all as cited.
- **The guard change is correct.** `DeliveryPlan` declares `changelog_base_url: str | None = None` (`src/routing/models.py:17`) and `DeliveryPlanResolver.resolve` fills it on every resolve (`src/routing/resolver.py:27`), so `base_url = plan.changelog_base_url` is always safe and the `getattr(..., None)` fallback was genuinely unreachable. `FakePlan` in the suite also carries the field, so the change is transparent to the tests.
- **Behavior parity around `changelog_client`.** Making all eight collaborators required (dropping the `changelog_client is not None` clause to leave `app_available = bool(base_url)`) is behavior-preserving: `main.py` wires `changelog_client` in the same guarded block as the other seven, so it was never `None` at runtime when the fan-out ran. In the suite, every case that omits `changelog_client` also leaves `changelog_base_url=None`, so `app_available` short-circuits before the `None` client is ever touched — no case breaks.
- **Dispatch/isolation parity.** `release_delivery.deliver` is a bound `Callable[[PushEvent], Awaitable[None]]`, matching `_run_isolated`'s `task(event)` contract; the `"release_delivery"` label and the skip log line are preserved verbatim.
- **Import removals are safe.** `functools` and `ChangelogEntry` are used in the router only by the fan-out; `role_for_branch` / `BranchRole` remain used by the role dispatch. `main.py` still needs `functools` for `build_release_report` — untouched.
- **No stray callers.** A repo-wide search for `_deliver_release` / `_ENVIRONMENT_BY_ROLE` / `release_delivery` finds references only in `router.py` and the test file — all covered by the plan.
- **Test move target is real.** `tests/delivery/` already exists with `__init__.py`; the async suite drives fakes only and depends on no `tests/ingestion/` fixtures, so the move is clean and needs no LLM/tunnel.
- **No migration / security surface.** Pure code relocation — no schema, no DB, no change to signature verification or auth.

### Positive Notes

- The `TYPE_CHECKING` + string-annotation decision for `Report`/`PushEvent` is exactly right and explicitly anchored to an existing in-repo pattern — it keeps the two new cross-feature edges type-only and cycle-free rather than pulling `changelog`/`ingestion` into `delivery`'s runtime graph.
- Retaining the twelve behavior cases unchanged in intent, and naming them as the proof of zero behavior change, is the correct discipline for an extraction; the plan resists the temptation to "improve" coverage mid-refactor.
- The presence gate is thoughtfully split: composition-root construction (only inside the guarded block) plus the router's `getattr(..., "release_delivery", None)` fetch together reproduce the old all-collaborators-present gate without re-checking inside the class.
- Task dependencies (1 → 2 → 3, 1 → 4, 3+4 → 5) are correctly ordered and the final task verifies against the retargeted suite.

### Minor (non-blocking, no action required)

- Task 1's "Add the imports the moved code needs" bullet enumerates only the moved-method-body imports (`PushEvent`, `ChangelogEntry`, `BranchRole`, `role_for_branch`, `logging`). The five runtime constructor-annotation types (`RepoMirror`, `DeliveryPlanResolver`, `Versioner`, `Localizer`, `GitHubReleaseClient`) are each named with their source module inline in the constructor bullet, so an implementer has everything needed — the info is simply split across two bullets rather than consolidated. No correctness impact.

PLAN_REVIEW_PASS
