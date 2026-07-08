# 12.1 — Changelog protocol client + frozen contract

**Phase:** 12 — Internal protocol (changelog channel). First task. Herald's side of the contract toward integrated apps — everything Herald controls; the app's implementation is out of scope.

## Current state

The internal protocol is described in `docs/spec/delivery.md#internal-protocol` (two endpoints, no keys, internal network) but has no authoritative contract artifact and no client. The delivery layer (Phase 9) posts to Telegram and (Phase 11) cuts GitHub releases; there is no changelog channel.

## Change

Freeze the contract as an authoritative artifact and add the client that speaks it.

- `contract/changelog.openapi.yaml` — the single cross-cutting invariant: `GET /internal/changelog/config → { "languages": ["ru", ...] }` and `POST /internal/changelog/entry` with `{ version, environment, summaries: { "<lang>": "<text>", ... }, github_url }` → `201`. `summaries` is a map keyed by language code, one entry per language the app declared in `config` — no language is hardcoded in the contract. This is the contract an integrating app implements; freezing it here makes it the reference for both sides.
- Extend `src/core/config.py` `Settings` with `repo_apps` — a `repo → internal base URL` map.
- Extend `DeliveryPlan` (9.1) with `changelog_base_url: str | None`, and extend `DeliveryPlanResolver` to fill it on a `staging`/`release` push from `Settings.repo_apps` (the repo's mapped URL, or `None`). The changelog target is **plan-state resolved through the seam**, exactly like `telegram_channel` — the delivery code (11.3, 12.2) reads `plan.changelog_base_url`, never `Settings.repo_apps` inline (per `docs/spec/delivery.md`'s resolver-state table).
- `src/delivery/changelog_client.py` — `ChangelogClient`:
  - `config(base_url: str) -> list[str]` — `GET {base_url}/internal/changelog/config`, return the declared languages.
  - `entry(base_url: str, payload: ChangelogEntry) -> None` — `POST {base_url}/internal/changelog/entry`. `ChangelogEntry` carries `summaries: dict[str, str]`, not fixed `ru`/`en` fields.
  - `httpx`, no API key (the internal network is the trust boundary).

## Files & types

- new `contract/changelog.openapi.yaml`
- edit `src/core/config.py` (`repo_apps`)
- edit `src/routing/models.py` / `src/routing/resolver.py` (`DeliveryPlan.changelog_base_url` + the resolver fills it from `repo_apps`)
- new `src/delivery/changelog_client.py` (`ChangelogClient`, `ChangelogEntry`)

## Guards

- The client matches the frozen OpenAPI exactly — the payload shape and endpoints are the invariant.
- **No language is privileged or fixed in the contract** — `summaries`' key set is whatever the app declared via `config`, not a hardcoded `ru`/`en` pair.
- No API key — access is the internal network; the base URL comes from `repo_apps` config.
- Transport/non-2xx errors raise, never a silent success.
- The changelog target flows through the resolver into `DeliveryPlan.changelog_base_url`; features read the plan, never `Settings.repo_apps` directly — the resolver seam holds, so the config store can move to a database / GUI (Phase 14) without touching delivery code.

## Verification

- Against a **stub** implementing the two endpoints: `config(base_url)` returns the stub's declared languages; `entry(base_url, payload)` posts a well-formed entry and the stub returns `201`.
- The stub validates the posted body against `contract/changelog.openapi.yaml`.
- **Mandatory test against the stub, varying its declared-language count (1, 2, 3):** the posted `entry`'s `summaries` key set equals **exactly** the languages the stub declared via `config` — never a fixed `{ru, en}` pair. A hardcoded pair would satisfy every other test while silently dropping a third declared language.
