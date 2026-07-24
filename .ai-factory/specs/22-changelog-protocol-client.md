# 12.1 — Changelog protocol client + frozen contract

**Phase:** 12 — Internal protocol (changelog channel). First task. Herald's side of the contract toward integrated apps — everything Herald controls; the app's implementation is out of scope.

## Current state

The internal protocol is described in `docs/behavior/delivery.md#internal-protocol` (two endpoints, no keys, internal network) but has no authoritative contract artifact and no client. The delivery layer (Phase 9) posts to Telegram and (Phase 11) cuts GitHub releases; there is no changelog channel.

## Change

Freeze the contract as an authoritative artifact and add the client that speaks it.

- `contract/changelog.openapi.yaml` — the single cross-cutting invariant, with field schemas pinned:
  - `GET /internal/changelog/config` → `200 { languages: [string] }`.
  - `POST /internal/changelog/entry` request body: `version: string` (example `"v1.2.0"` — the canonical `Version.__str__` render, 11.1, `v`-prefixed, per `docs/behavior/delivery.md#versioning`'s "same token everywhere"), `environment: string enum [staging, production]`, `summaries: object, additionalProperties: string` (one entry per language the app declared in `config` — no language hardcoded in the contract), `github_url: string, format: uri`. Response: `201`.
  - This is the contract an integrating app implements; freezing it here makes it the reference for both sides.
- Extend `src/core/config.py` `Settings` with `repo_apps: Annotated[dict[str, str], NoDecode] = {}` — a `{"<repo>": "<base_url>"}` map, added to the **existing** `_parse_json_dict` `@field_validator` field list (`src/core/config.py:25,42-49`), mirroring `canonical_refs` exactly (same `dict[str,str]` shape, same JSON parse). Key = the **bare `push.repo` string, never `org/repo`** — the same repo-key invariant `canonical_refs`/`Chunk.repo`/`Edge.to_repo` already follow.
- Extend `DeliveryPlan` (9.1) with `changelog_base_url: str | None`, and extend `DeliveryPlanResolver` to fill it **unconditionally on every `resolve`** from `Settings.repo_apps` (the repo's mapped URL, or `None`) — a free dict lookup, exactly like 9.3's `telegram_channel`/`language` (`16-telegram-delivery.md:14`), NOT gated on branch role inside the resolver. The caller's existing staging/release gate (11.3/12.2) is the only gate on whether the changelog channel actually fires. The changelog target is **plan-state resolved through the seam** — the delivery code (11.3, 12.2) reads `plan.changelog_base_url`, never `Settings.repo_apps` inline (per `docs/behavior/delivery.md`'s resolver-state table).
- `src/delivery/changelog_client.py`:
  - `ChangelogEntry(version: str, environment: str, summaries: dict[str, str], github_url: str)` — 1:1 with the frozen `{version, environment, summaries, github_url}`, not fixed `ru`/`en` fields.
  - `ChangelogClient`:
    - `config(base_url: str) -> list[str]` — `GET {base_url}/internal/changelog/config`, return the declared languages.
    - `entry(base_url: str, payload: ChangelogEntry) -> None` — `POST {base_url}/internal/changelog/entry`.
  - `httpx`, no API key (the internal network is the trust boundary), an explicit request timeout (matching the transport discipline of `OllamaClient`/`GitHubAppAuth`, both of which set one rather than blocking indefinitely).

## Files & types

- new `contract/changelog.openapi.yaml`
- edit `src/core/config.py` (`repo_apps: Annotated[dict[str, str], NoDecode]`, added to `_parse_json_dict`'s field list)
- edit `src/routing/models.py` / `src/routing/resolver.py` (`DeliveryPlan.changelog_base_url` + the resolver fills it unconditionally from `repo_apps`)
- new `src/delivery/changelog_client.py` (`ChangelogClient`, `ChangelogEntry(version, environment, summaries, github_url)`)

## Guards

- The client matches the frozen OpenAPI exactly — the payload shape and endpoints are the invariant.
- **No language is privileged or fixed in the contract** — `summaries`' key set is whatever the app declared via `config`, not a hardcoded `ru`/`en` pair.
- No API key — access is the internal network; the base URL comes from `repo_apps` config; `repo_apps` keyed by the bare repo name, never `org/repo`.
- Transport/non-2xx errors raise, never a silent success; requests carry an explicit timeout.
- `version` on the wire is always `str(version)` (11.1's canonical `Version.__str__`), `v`-prefixed — the same token the GitHub tag and Telegram header carry, never stripped or reformatted here.
- `DeliveryPlanResolver` fills `changelog_base_url` on **every** `resolve` call, unconditionally — branch-role gating happens only at the caller (11.3/12.2), never a second time inside the resolver.
- The changelog target flows through the resolver into `DeliveryPlan.changelog_base_url`; features read the plan, never `Settings.repo_apps` directly — the resolver seam holds, so the config store can move to a database / GUI (Phase 14) without touching delivery code.

## Verification

- Against a **stub** implementing the two endpoints: `config(base_url)` returns the stub's declared languages; `entry(base_url, payload)` posts a well-formed entry and the stub returns `201`.
- The stub asserts the posted body's field set/shape against `contract/changelog.openapi.yaml` by hand (no OpenAPI/JSON-schema validator dependency — `pyproject.toml` has no such package today; this task adds none).
- **Mandatory test against the stub, varying its declared-language count (1, 2, 3):** the posted `entry`'s `summaries` key set equals **exactly** the languages the stub declared via `config` — never a fixed `{ru, en}` pair. A hardcoded pair would satisfy every other test while silently dropping a third declared language.
