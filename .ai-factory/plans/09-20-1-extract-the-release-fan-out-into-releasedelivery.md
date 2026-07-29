# Plan: 20.1 — Extract the release fan-out into `ReleaseDelivery`

## Context
Move the ~85-line `_deliver_release` orchestration out of the webhook router into a new `ReleaseDelivery` class in `src/delivery/service.py`, with its collaborators typed and constructor-injected at the composition root, exposing one method the router awaits — with zero behavior change.

## Settings
- Testing: yes (retarget the existing 12-case behavior suite at the new class — no new coverage)
- Logging: minimal (preserve every existing log line verbatim)
- Docs: no

## Tasks

### Phase 1: Extract the orchestration into `ReleaseDelivery`

- [x] **Task 1: Add `ReleaseDelivery` alongside `DeliveryService` in `src/delivery/service.py`**
  Files: `src/delivery/service.py`
  Add a new `ReleaseDelivery` class in the same module as `DeliveryService`. Move the body of `_deliver_release` (router lines 47–129) into a single async method `async def deliver(self, event: PushEvent) -> None`.
  - Constructor takes the eight collaborators as typed, injected dependencies (all required — no per-call kwargs, no defaults):
    - `mirror: RepoMirror` (from `src.github.mirror`)
    - `delivery_plan_resolver: DeliveryPlanResolver` (from `src.routing.resolver`)
    - `versioner: Versioner` (from `src.versioning.versioner`)
    - `build_release_report: Callable[[str, int, str], Report]` (`Report` from `src.changelog.report`)
    - `localizer: Localizer` (from `src.reasoning.localizer`)
    - `github_release_client: GitHubReleaseClient` (from `src.delivery.github_release`)
    - `delivery_service: DeliveryService` (same module)
    - `changelog_client: ChangelogClient` (from `src.delivery.changelog_client`)
    Store each on a private attribute (`self._mirror`, etc.), following the constructor-DI pattern already used by `DeliveryService`, `Summarizer`, etc.
  - Move the module-level constant `_ENVIRONMENT_BY_ROLE = {BranchRole.STAGING: "staging", BranchRole.RELEASE: "production"}` into `service.py` (it is only used by the fan-out).
  - Add the imports the moved code needs: `PushEvent` (from `src.ingestion.models`), `ChangelogEntry` (from `src.delivery.changelog_client`), `BranchRole` and `role_for_branch` (from `src.routing.models` / `src.routing.resolver`), plus `logging` (already present). To keep the `delivery → changelog`/`delivery → ingestion` type-only edges clean and avoid any import cycle, import `Report` and `PushEvent` under a `TYPE_CHECKING` guard with string annotations, mirroring the pattern in `src/changelog/release.py`.
  - Preserve the fan-out's docstring (adapt its wording from "module-level function" to the class/method) so the graceful-degradation contract stays documented on the class.
  - **Behavior must be identical**: same legs in the same order (mirror ensure → `versioner.next` → no-version early return → resolve plan → language union → optional changelog `config` → `build_release_report` → `localizer.report_notes` → `github_release_client.create` → `delivery_service.deliver` → optional changelog `entry`), same `BranchRole.STAGING` → prerelease flag, same `_ENVIRONMENT_BY_ROLE[role]` mapping, same two `try/except` graceful-degradation blocks around `config` and `entry`, and every `logger.info` / `logger.exception` message and its format args preserved character-for-character.
  - **Guard change**: read the changelog base URL as a plain attribute `base_url = plan.changelog_base_url` — NOT `getattr(plan, "changelog_base_url", None)`. `DeliveryPlan` declares `changelog_base_url: str | None = None` and the resolver fills it on every resolve, so the attribute is always present; keep `app_available = bool(base_url)` as the mapped/unmapped gate.
  - The class assumes it is only ever called with all collaborators wired — do NOT re-check collaborator presence inside `deliver`.

### Phase 2: Thin the router and wire at the composition root

- [x] **Task 2: Build and store `ReleaseDelivery` at the composition root** (depends on Task 1)
  Files: `src/main.py`
  Inside the existing `if (settings.github_app_id ... )` block in `lifespan` — after `delivery_service`, `changelog_client`, and `build_release_report` are assigned — construct one `ReleaseDelivery` with every collaborator injected and store it on `app.state.release_delivery`:
  ```python
  app.state.release_delivery = ReleaseDelivery(
      mirror=mirror,
      delivery_plan_resolver=app.state.delivery_plan_resolver,
      versioner=app.state.versioner,
      build_release_report=app.state.build_release_report,
      localizer=app.state.localizer,
      github_release_client=app.state.github_release_client,
      delivery_service=app.state.delivery_service,
      changelog_client=app.state.changelog_client,
  )
  ```
  Add `ReleaseDelivery` to the existing `from src.delivery.service import ...` import. Because this lives inside the same guarded block, `app.state.release_delivery` is set only when all collaborators are wired and is simply absent otherwise — this is the composition-root half of the presence gate.

- [x] **Task 3: Remove the fan-out from the router and dispatch the injected instance** (depends on Task 2)
  Files: `src/ingestion/router.py`
  - Delete the `_deliver_release` function (lines 47–129) and the `_ENVIRONMENT_BY_ROLE` constant (moved to `service.py`).
  - In `receive_github_webhook`, replace the collaborator-dictionary gate (the `state`/`collaborators`/`functools.partial` block, lines 212–233) with a fetch of the pre-built instance:
    ```python
    role = role_for_branch(event.branch)
    if role in (BranchRole.STAGING, BranchRole.RELEASE):
        release_delivery = getattr(request.app.state, "release_delivery", None)
        if release_delivery is not None:
            background_tasks.add_task(_run_isolated, "release_delivery", release_delivery.deliver, event)
        else:
            logger.info(
                "release delivery skipped: required collaborators absent (org_id=%s repo=%s)",
                event.org_id, event.repo,
            )
    ```
    This keeps the presence gate in the router, keeps the `"release_delivery"` isolation label and the `_run_isolated` wrapper unchanged, and preserves the skip log line verbatim.
  - Remove now-unused imports: `functools` and `from src.delivery.changelog_client import ChangelogEntry`. Keep `role_for_branch` and `BranchRole` (still used by the role dispatch and by other push handling). `_CREATION_BEFORE_SHA` stays in the router (used by `_parse_push_event`).
  - After this the router contains only: receive, `_verify_signature`, `_parse_push_event`, `_parse_installation_event`, the two isolation wrappers, and the dispatch — no orchestration logic.

### Phase 3: Retarget the behavior suite

- [x] **Task 4: Point the 12-case suite at `ReleaseDelivery`** (depends on Task 1)
  Files: `tests/ingestion/test_release_delivery.py` (move to `tests/delivery/test_release_delivery.py`, since the subject now lives in the delivery feature)
  - Change the import from `from src.ingestion.router import _deliver_release` to `from src.delivery.service import ReleaseDelivery`.
  - Update the `_collaborators` helper so it constructs and returns a `ReleaseDelivery` instance built from the fakes (passing the same eight collaborators to the constructor) instead of returning a kwargs dict; each test then calls `await release_delivery.deliver(_event(...))` instead of `await _deliver_release(_event(...), **kwargs)`, while still exposing the individual fakes to the test for assertions.
  - Keep all twelve cases intact and unchanged in intent — leg order, single language-union resolution feeding every channel, graceful degradation at both changelog calls, prerelease-per-role, no-version skip, and the no-re-derivation assertions. None dropped, weakened, or merged. The suite is the proof that the extraction changed no behavior.
  - Update the module docstring's reference from "`_deliver_release`, the module-level fan-out" to the `ReleaseDelivery.deliver` method. `FakePlan` and its comment need no change.

- [x] **Task 5: Run the suite** (depends on Task 3, Task 4)
  Files: (none — verification)
  Run `make test` and confirm the retargeted release-delivery suite and the rest of the suite pass. No LLM/tunnel needed — the suite drives fakes only.
