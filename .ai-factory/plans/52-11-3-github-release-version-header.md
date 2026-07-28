# Plan: 11.3 — GitHub release + version header

## Context
Close Phase 11: on a `staging`/`release` push, resolve the required-language union once, build the release note once via `Localizer.report_notes`, cut a GitHub release in `plan.github_release_language`, and head the Telegram message with the version in `plan.language` — all inside one isolated background task that `mirror.ensure`s first.

## Settings
- Testing: yes
- Logging: minimal
- Docs: no

## Assumptions & pinned decisions

- **12.1 is not built yet** (roadmap order 11.3 < 12.1). `DeliveryPlan.changelog_base_url`, `Settings.repo_apps`, and the `ChangelogClient` concrete belong to 12.1 and do **not** exist in the code today (verified: no `changelog_base_url` / `ChangelogClient` references in `src/`). So 11.3 builds the union-resolution + fan-out with the **changelog-app leg present but dormant**: the app base URL is read via `getattr(plan, "changelog_base_url", None)` (None-safe on the current frozen `DeliveryPlan`, and automatically live once 12.1 adds the field), and the changelog client is an **optional injected collaborator that defaults to `None`** until 12.1 wires the concrete. When either is absent the union stays the fixed-channel languages `{plan.language, plan.github_release_language}`. The mandatory union/degradation behaviour is still fully implemented and tested now using fakes — no dependency on 12.1's concrete types.
- **`config` shape:** the changelog client's `config(base_url)` is awaited and treated as returning an object exposing `.languages: list[str]`. This must be reconciled against 12.1's frozen contract (`GET config → {languages:[string]}`) when 12.1 lands; if 12.1 returns a mapping instead of an object, adapt the single accessor in the union step. Pinned here so the fan-out and its tests are unambiguous.
- **`GitHubReleaseClient.create` needs `org_id` to mint the installation token** (`GitHubAppAuth.token(org_id)`), but the spec's listed parameters are the *release-body* fields and omit it. Decision: add `org_id: int` as the first parameter of `create`, threaded from `event.org_id`; `owner` stays `event.org_login`. (`event` carries both — `src/ingestion/models.py`.)
- **Fan-out location:** per the spec (the union/notes are "local values inside the single staging/release handler in `src/ingestion/router.py`", and `Files & types` lists no new service file), the fan-out body is a module-level async function in `src/ingestion/router.py`, registered as one isolated background task exactly like `knowledge_sync.on_push`. The router only *sequences* injected collaborators (versioner, localizer, clients, delivery service) — no business logic beyond the sequence, the union set-math, and the `config` try/except — so it stays within the thin-entry-point rule. Collaborators are wired at the composition root (`src/main.py` lifespan) and reached via `request.app.state`.

## Tasks

### Phase 1: Primitives (data, release client, header)

- [x] **Task 1: Add `github_release_language` to `DeliveryPlan`**
  Files: `src/routing/models.py`
  Add `github_release_language: str = "en"` immediately after `language`, mirroring the `language: str = "ru"` field — a configured default, never a literal in the union code. Do **not** touch `DeliveryPlanResolver` (`src/routing/resolver.py`): the dataclass default supplies the value, matching how `Files & types` scopes the edit to `models.py` only.

- [x] **Task 2: `GitHubReleaseClient`**
  Files: `src/delivery/github_release.py` (new)
  New class `GitHubReleaseClient` constructed with `auth: GitHubAppAuth`. Method:
  `async def create(self, org_id: int, owner: str, repo: str, version: Version, body: str, prerelease: bool, target_commitish: str) -> str`.
  Mint the token with `self._auth.token(org_id)`. Use `httpx.AsyncClient(base_url="https://api.github.com", headers=...)` with headers mirroring `GitHubAppAuth`'s request shape (`src/github/app_auth.py:65-70`): `Authorization: Bearer <installation token>`, `Accept: application/vnd.github+json`, plus `X-GitHub-Api-Version: 2022-11-28`. `POST /repos/{owner}/{repo}/releases` with JSON body `{"tag_name": str(version), "name": str(version), "target_commitish": target_commitish, "body": body, "prerelease": prerelease}` — `tag_name` is the canonical `Version.__str__` render (`src/versioning/versioner.py`), never formatted independently. `response.raise_for_status()` (non-2xx raises). Return `response.json()["html_url"]`. Import `Version` from `src.versioning.versioner`.

- [x] **Task 3: Version header on the Telegram delivery**
  Files: `src/delivery/service.py`
  Extend `DeliveryService.deliver` to `async def deliver(self, plan: DeliveryPlan, note: str, version: "Version | None" = None) -> None`. Keep the existing channel-`None` skip. When `version is not None`, prepend the header: send `f"{version}\n\n{note}"` (header = `str(version)`, the canonical render); when `version is None`, behaviour is unchanged (the Phase-10 report path calls `deliver` with no version → no header). Import `Version` from `src.versioning.versioner`. No branch-role check here — the header is keyed purely on `version` presence (a version only ever exists for a staging/release push).

### Phase 2: Fan-out orchestration & wiring

- [x] **Task 4: Release-delivery fan-out function** (depends on Tasks 1–3)
  Files: `src/ingestion/router.py`
  Add a module-level `async def _deliver_release(event: PushEvent, *, mirror, delivery_plan_resolver, versioner, build_release_report, localizer, github_release_client, delivery_service, changelog_client=None) -> None`. Body, in order (mirrors the spec's fan-out sequence):
  1. `role = role_for_branch(event.branch)` (import from `src.routing.resolver`).
  2. `mirror.ensure(event.repo, event.org_id)` — **first**, never relying on `knowledge_sync` having ensured (background-task order is not a contract; `knowledge_sync` may be absent).
  3. `version = versioner.next(event.repo, role, event.before, event.after)`; if `version is None` → `return` (nothing cut, no header — the back-merge/skip case).
  4. `plan = delivery_plan_resolver.resolve(event.org_id, event.repo, event.branch)`.
  5. Resolve the union: `union = {plan.language, plan.github_release_language}`. `base_url = getattr(plan, "changelog_base_url", None)`; if `changelog_client is not None and base_url`: `try: union |= set((await changelog_client.config(base_url)).languages)` `except Exception: logger.exception(...)` and leave the union at the fixed-channel languages (app dropped from this delivery; the changelog channel is 12.2's concern). Keep an `app_available` local flag for 12.2.
  6. `report = build_release_report(event.repo, event.org_id, event.branch)` (a partial over `release_report` with `mirror`/`collector`/`resolver`/`reasoner` bound — see Task 5).
  7. `notes = await localizer.report_notes(report, event.repo, event.org_id, union)` — **exactly once**; feeds every channel.
  8. `github_url = await github_release_client.create(event.org_id, event.org_login, event.repo, version, notes.get(plan.github_release_language) or "", role is BranchRole.STAGING, event.after)` — `prerelease` via `role` (STAGING→`True`, RELEASE→`False`), never an inline branch string compare; `target_commitish=event.after`. `notes.get(...) or ""` guards the (rare) empty-report body. Log the created URL; capture `github_url` for 12.2's changelog `entry`.
  9. `await delivery_service.deliver(plan, notes.get(plan.language) or "", version=version)`.
  Import `BranchRole` from `src.routing.models`. Leave a short comment marking step 8/9's locals (`github_url`, `union`, `notes`, `app_available`) as the extension point 12.2 continues in — no `entry` call in 11.3.

- [x] **Task 5: Wire release-delivery collaborators at the composition root** (depends on Tasks 2–3)
  Files: `src/main.py`
  Inside the existing `if github_app… mirror` block of `lifespan` (where `mirror`, `collector`, the `LinkedChangeResolver`, `auth`, `embedder`, `store`, `episodic_store`, `graph` already exist), build and expose on `app.state`:
  - `app.state.mirror = mirror`.
  - `llm = OllamaClient(settings.ollama_url, settings.ollama_model, settings.ollama_api_key)` and `reasoner = Reasoner(llm=llm, embedder=embedder, knowledge=store, episodic=episodic_store, graph=graph, reasoner_k=settings.reasoner_k)` — mirroring `scripts/report.py`'s wiring.
  - `app.state.localizer = PivotLocalizer(reasoner, LLMTranslator(llm), pivot=settings.pivot_lang)`.
  - `app.state.versioner = Versioner(mirror, collector, settings.version_increment)`.
  - `app.state.github_release_client = GitHubReleaseClient(auth)`.
  - `app.state.delivery_service = DeliveryService(TelegramClient(settings.telegram_bot_token))`.
  - `app.state.build_release_report = functools.partial(release_report, mirror=mirror, collector=collector, resolver=<the LinkedChangeResolver>, reasoner=reasoner)` (collapses the four `release_report` collaborators to one call `build_release_report(repo, org_id, branch)`).
  `app.state.delivery_plan_resolver` already exists. Do **not** create `changelog_client` (12.1 owns it) — the router reads it via `getattr(..., None)`. Add the imports (`functools`, `OllamaClient`, `Reasoner`, `LLMTranslator`, `PivotLocalizer`, `Versioner`, `GitHubReleaseClient`, `DeliveryService`, `TelegramClient`, `release_report`). The GitHub-App-disabled `else` branch leaves these attrs absent, so the router's presence check (Task 6) skips the fan-out.

- [x] **Task 6: Register the fan-out on staging/release pushes** (depends on Tasks 4–5)
  Files: `src/ingestion/router.py`
  In `receive_github_webhook`, in the `event_name == "push"` branch after the `episodic_writer` registration, compute `role = role_for_branch(event.branch)` and, when `role in (BranchRole.STAGING, BranchRole.RELEASE)`, gather the release collaborators from `request.app.state` via `getattr(..., None)` (`mirror`, `delivery_plan_resolver`, `versioner`, `build_release_report`, `localizer`, `github_release_client`, `delivery_service`; `changelog_client` optional). If all required ones are present, build `task = functools.partial(_deliver_release, mirror=…, delivery_plan_resolver=…, versioner=…, build_release_report=…, localizer=…, github_release_client=…, delivery_service=…, changelog_client=getattr(request.app.state, "changelog_client", None))` and `background_tasks.add_task(_run_isolated, "release_delivery", task, event)` — one isolated task, mirroring the `knowledge_sync.on_push`/`episodic_writer.write` registrations. If a required collaborator is missing (App disabled), log and skip. The `return JSONResponse(...)` response path is unchanged (the webhook still responds promptly). Import `functools`.

### Phase 3: Tests

- [x] **Task 7: Fan-out behaviour tests** (depends on Task 4)
  Files: `tests/ingestion/test_release_delivery.py` (new)
  Drive `_deliver_release` directly with mocked collaborators (`versioner`, `build_release_report`, `localizer.report_notes`, `github_release_client.create`, `delivery_service.deliver`, `mirror.ensure`). Assert:
  - **One resolution:** for a staging push with a version, `report_notes` is called **exactly once**; the union passed equals `{plan.language, plan.github_release_language}` (∪ the app's declared languages when a fake `changelog_client` + a plan carrying `changelog_base_url` are supplied — use a lightweight stand-in plan/config object so no 12.1 type is needed); `create` is called with `body == notes[plan.github_release_language]` and `delivery_service.deliver` with `note == notes[plan.language]` and `version` set.
  - **`mirror.ensure` runs first** (before version/report — assert call order).
  - **Role → prerelease:** staging → `create(..., prerelease=True, ...)`, release → `prerelease=False`; `target_commitish == event.after`; `owner == event.org_login`, `org_id == event.org_id`.
  - **`None` version:** `versioner.next` → `None` ⇒ `report_notes`/`create` not called and `delivery_service.deliver` not called with a version header (assert `create` uncalled and the deliver `version` arg is absent — the fan-out returns early).

- [x] **Task 8: Unreachable-app degradation test** (depends on Task 4)
  Files: `tests/ingestion/test_release_delivery.py`
  With a fake `changelog_client.config` that raises and a plan carrying `changelog_base_url`: assert the release is still cut (`create` called) and the version-headed Telegram delivered (`deliver` called with `version`); the union passed to `report_notes` is exactly `{plan.language, plan.github_release_language}`; and the app-unavailable path is taken (the changelog channel left for 12.2 — assert no crash and the fixed union). This pins the Phase-12 invariant that an unreachable app never blocks the other channels.
