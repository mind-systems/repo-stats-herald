# Plan: 12.1 — Changelog protocol client + frozen contract

## Context
Freeze the internal changelog protocol as an authoritative OpenAPI artifact and add Herald's client (`ChangelogClient`) that speaks it, plus the config (`Settings.repo_apps`) and resolver-seam (`DeliveryPlan.changelog_base_url`) plumbing that carries a mapped app's base URL through the delivery plan. Per spec `.ai-factory/specs/22-changelog-protocol-client.md` — only Herald's side of the two-endpoint contract; the app's implementation is verified against a stub, out of scope here.

## Settings
- Testing: yes (spec mandates tests against a stub; see Guards/Verification in the spec)
- Logging: minimal
- Docs: no

## Tasks

### Phase 1: Freeze the contract

- [x] **Task 1: Author `contract/changelog.openapi.yaml`**
  Files: `contract/changelog.openapi.yaml` (new)
  Create the `contract/` directory and freeze the internal protocol as an OpenAPI 3.x document. It is the single cross-cutting invariant — the reference both Herald's client and any integrating app implement. Define exactly two operations, both under `/internal/...`, no security scheme (the internal network is the trust boundary — no API key):
  - `GET /internal/changelog/config` → `200` with body `{ languages: [string] }` (array of language codes the app declares; no language value hardcoded — the schema is `type: array, items: {type: string}`).
  - `POST /internal/changelog/entry` request body:
    - `version`: `string` (example `"v1.2.0"` — the canonical `v`-prefixed `Version.__str__` render per `docs/behavior/delivery.md#versioning`'s "same token everywhere"; never stripped/reformatted).
    - `environment`: `string`, `enum: [staging, production]`.
    - `summaries`: `object` with `additionalProperties: {type: string}` — one entry per language the app declared in `config`; **no `ru`/`en` or any language fixed in the schema**.
    - `github_url`: `string`, `format: uri`.
    - Response: `201` (no response body required).
  Keep field names/shapes 1:1 with what the client sends (Task 4) — the payload shape and the two endpoint paths are the invariant the client must match exactly.

### Phase 2: Config + resolver seam

- [x] **Task 2: Add `Settings.repo_apps`**
  Files: `src/core/config.py`
  Add `repo_apps: Annotated[dict[str, str], NoDecode] = {}` to `Settings`, placed beside the other JSON-dict settings (`canonical_refs`, `github_org_logins`, `telegram_channels`, ~line 37-39). Add `"repo_apps"` to the **existing** `_parse_json_dict` `@field_validator` decorator field list (line 59) — do **not** write a new validator; it mirrors `canonical_refs` exactly (same `dict[str, str]` shape, same JSON-string parse). The map is `{"<repo>": "<base_url>"}` where the key is the **bare `push.repo` string, never `org/repo`** — the same repo-key invariant `canonical_refs`/`Chunk.repo`/`Edge.to_repo` already follow. No default language, no secret, base URLs only.

- [x] **Task 3: Carry `changelog_base_url` through the delivery plan** (depends on Task 2)
  Files: `src/routing/models.py`, `src/routing/resolver.py`, `tests/routing/test_role_for_branch.py`
  - In `DeliveryPlan` (`models.py`) add field `changelog_base_url: str | None = None` (keep it defaulted so existing `DeliveryPlan(...)` construction sites — e.g. the delivery-service tests — stay valid; place it alongside `telegram_channel`).
  - In `DeliveryPlanResolver.resolve` (`resolver.py`) fill it **unconditionally on every `resolve` call** from `self._settings.repo_apps.get(repo)` — a free dict lookup keyed by the bare `repo`, exactly like `telegram_channel=self._settings.telegram_channels.get(org_id)`. **Not** gated on `branch_role` inside the resolver: the staging/release firing gate lives only at the caller (11.3/12.2), never a second time here. The changelog target is now plan-state resolved through the seam, so downstream delivery code reads `plan.changelog_base_url`, never `Settings.repo_apps` inline.
  - **Add a resolver test** in `tests/routing/test_role_for_branch.py`, parallel to the existing sibling-mapping tests (`test_resolve_maps_numeric_org_id_to_its_channel` / `test_resolve_returns_none_channel_for_unmapped_org`, ~lines 43–59): assert `resolve` fills `changelog_base_url` from `repo_apps` keyed by the **bare repo** string, and yields `None` for an unmapped repo. This is a silent-failure surface — a swap to `repo_apps.get(org_id)` (int key vs the str keys `repo_apps` holds) would always miss and quietly resolve `None`, deactivating the whole changelog channel with no error — so the bare-repo key invariant must be verified, not just asserted in prose. Construct `Settings(github_webhook_secret="x", telegram_bot_token="x", repo_apps={"<repo>": "<base_url>"})` and call `resolve` with that bare repo and a mismatched one.

### Phase 3: Client

- [x] **Task 4: Add `ChangelogClient` + `ChangelogEntry`** (depends on Task 1)
  Files: `src/delivery/changelog_client.py` (new)
  Owned external boundary of the changelog feature, matching `contract/changelog.openapi.yaml` exactly. Follow the transport discipline of `OllamaClient`/`TelegramClient`/`GitHubReleaseClient` — `httpx.AsyncClient` with an explicit request timeout (constructor `timeout: float` default, e.g. `30.0`), `response.raise_for_status()` so transport/non-2xx errors raise (never a silent success), **no API key / no auth header** (internal network is the boundary).
  - `ChangelogEntry(version: str, environment: str, summaries: dict[str, str], github_url: str)` — a frozen dataclass, fields 1:1 with the frozen `{version, environment, summaries, github_url}`. Not fixed `ru`/`en` fields — `summaries` is an open `dict[str, str]`.
  - `ChangelogClient`:
    - `async def config(self, base_url: str) -> list[str]` — `GET {base_url}/internal/changelog/config`, return the `languages` array from the response.
    - `async def entry(self, base_url: str, payload: ChangelogEntry) -> None` — `POST {base_url}/internal/changelog/entry` with JSON body `{version, environment, summaries, github_url}`. `version` is placed on the wire verbatim as a `str` — the caller passes `str(version)` (11.1's canonical `Version.__str__`); this client never strips or reformats the `v` prefix.
  The client takes the `base_url` per call (it is plan-state, resolved per push), holds no config itself, and constructs no concretes it should not own — consistent with the composition-root wiring pattern.

### Phase 4: Verification tests

- [x] **Task 5: Stub-based tests for `ChangelogClient`** (depends on Task 4)
  Files: `tests/delivery/test_changelog_client.py` (new)
  Verify against a **stub** implementing the two endpoints, following the existing `tests/delivery/test_telegram_client.py` monkeypatch-of-`httpx.AsyncClient` style (a fake async-context-manager client that routes on method+URL, records the POST body, and returns configured responses). No OpenAPI/JSON-schema validator dependency — assert the posted body's field set/shape **by hand** against `contract/changelog.openapi.yaml` (`pyproject.toml` adds no such package).
  - `config(base_url)` returns the stub's declared `languages` list.
  - `entry(base_url, payload)` posts to `.../internal/changelog/entry` a well-formed body whose keys are exactly `{version, environment, summaries, github_url}`, with `version` carried through verbatim (`v`-prefixed), `environment` one of `staging`/`production`; the stub returns `201`.
  - **Mandatory language-count test — vary the stub's declared-language count (1, 2, 3):** the posted `entry`'s `summaries` key set equals **exactly** the languages the stub declared via `config`, never a fixed `{ru, en}` pair (a hardcoded pair would pass every other assertion while silently dropping a third declared language).
  - A non-2xx / transport error from either endpoint raises (is not swallowed), mirroring the telegram-client error test.
