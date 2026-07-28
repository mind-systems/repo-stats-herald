# Plan: 12.2 — Changelog channel wiring

## Context
Fire the changelog channel on a staging/release push to a mapped repo (`plan.changelog_base_url` set, version ≠ `None`, app available), by posting a `ChangelogEntry` from `_deliver_release` as the last leg of 11.3's single isolated background task — reusing the languages/notes 11.3 already resolved, never re-deriving them, and never blocking the GitHub release or Telegram send.

## Ground-truth deviations from the spec (read before implementing)
Verified against the code, which overrides the spec's file hints where they disagree:

1. **The activation logic lives in `src/ingestion/router.py::_deliver_release`, not `src/delivery/service.py`.** The spec's Files list names `service.py`, but 11.3 placed the entire release fan-out (mirror-ensure → version → `config`/union → `report_notes` → GitHub release → Telegram) in the module-level `_deliver_release` in `router.py`. That function already holds every local the `entry` call needs (`role`, `version`, `base_url`, `app_available`, `github_url`, `notes`) and carries an explicit extension-point comment (`router.py:93-95`) marking exactly where `entry` goes. `DeliveryService` is a Telegram-only transport constructed with just a `TelegramClient`; grafting a second protocol client onto it would split the changelog protocol across two modules. Per the composition-root and "features orchestrate their own transports" patterns, the `entry` leg is added inline in `_deliver_release`. **`src/delivery/service.py` needs no change.**

2. **`app.state.changelog_client` is never registered at the composition root** (`src/main.py`). The router already threads `changelog_client=getattr(state, "changelog_client", None)` into the `_deliver_release` partial (`router.py:192`), but nothing sets it, so it is always `None` and the channel is dormant. This is a primary reason "the channel doesn't fire" and MUST be fixed in `main.py`.

3. **Latent contract-drift bug in `_deliver_release`'s `config` consumption.** The frozen client `ChangelogClient.config` returns `list[str]` (`src/delivery/changelog_client.py:27`, spec 22), but `_deliver_release` reads `union |= set(config.languages)` (`router.py:76`). Against the real registered client this raises `AttributeError`, is swallowed by the `except`, and permanently forces `app_available = False` — so once the client is registered (fix #2) the channel would still never fire. The existing test's `FakeChangelogClient.config` returns a `FakeChangelogConfig` object with `.languages`, masking the drift. This is corrected here: consume `config` as a `list[str]` and align the test fake with the frozen contract.

## Settings
- Testing: yes (spec 23 mandates zero-re-derivation, declared-languages, unreachable-at-entry, and unmapped-repo tests)
- Logging: minimal
- Docs: no

## Tasks

### Phase 1: Wire the changelog client at the composition root

- [x] **Task 1: Register `ChangelogClient` in the web-app composition root**
  Files: `src/main.py`
  Add `from src.delivery.changelog_client import ChangelogClient`. Inside the `lifespan` `if (settings.github_app_id ...)` block — alongside `app.state.github_release_client` / `app.state.delivery_service` (~line 112-113), since the changelog channel only fires when the rest of the release-delivery collaborators exist — add `app.state.changelog_client = ChangelogClient()` (default timeout, mirroring how `github_release_client`/`delivery_service` are constructed at the root). Do not read `Settings.repo_apps` here — the base URL is plan-state, resolved through `DeliveryPlanResolver` into `plan.changelog_base_url` (12.1). No new setting is introduced.

### Phase 2: Activate the entry leg in the release fan-out

- [x] **Task 2: Consume `config` as `list[str]` and capture the declared languages** (depends on Task 1)
  Files: `src/ingestion/router.py`
  In `_deliver_release`, fix the `config`-reading block (currently `router.py:70-78`). Introduce a local `declared_languages: list[str] = []` before the `try`. Inside the `try`, replace `config = await changelog_client.config(base_url)` / `union |= set(config.languages)` with:
  ```python
  declared_languages = await changelog_client.config(base_url)
  union |= set(declared_languages)
  ```
  `ChangelogClient.config` returns a `list[str]` (frozen contract, `changelog_client.py:27`), so `.languages` is wrong. On failure `declared_languages` stays `[]` and `app_available` is set `False` exactly as today — the release + Telegram proceed on the fixed-channel union. Keep the existing `logger.exception(...)` unavailable-path message. This is the *only* `config` call; no second call is added anywhere.

- [x] **Task 3: Post the `ChangelogEntry` as the last leg of the fan-out** (depends on Task 2)
  Files: `src/ingestion/router.py`
  Add `from src.delivery.changelog_client import ChangelogEntry` (`BranchRole` is already imported at `router.py:15` — do not re-add it). Add a module-level constant so the environment mapping lives in exactly one place:
  ```python
  _ENVIRONMENT_BY_ROLE = {BranchRole.STAGING: "staging", BranchRole.RELEASE: "production"}
  ```
  Replace the extension-point comment block (`router.py:93-95`). Order inside `_deliver_release` stays: GitHub release → Telegram (`delivery_service.deliver`) → **then** the changelog entry as the final leg (it needs `github_url`, and must run after the release/Telegram are already delivered). After the existing `await delivery_service.deliver(...)` call, append:
  ```python
  if app_available:
      try:
          await changelog_client.entry(
              base_url,
              ChangelogEntry(
                  version=str(version),
                  environment=_ENVIRONMENT_BY_ROLE[role],
                  summaries={lang: notes[lang] or "" for lang in declared_languages},
                  github_url=github_url,
              ),
          )
      except Exception:
          logger.exception(
              "changelog entry failed for repo=%s org_id=%s", event.repo, event.org_id
          )
  ```
  Notes on the guards this satisfies, all met by reusing existing locals (zero re-derivation):
  - `version` is already guaranteed non-`None` (the function returns early at `router.py:62-65` on a back-merge/`None` version), so a `None` version delivers no entry.
  - `app_available` already encodes "mapped repo (`base_url` set) **and** `config` succeeded" — an unmapped repo (`base_url` `None`) or an unavailable app never reaches `entry`.
  - `role` is the same `role` local resolved once at the top of `_deliver_release` (`router.py:55`) — no second `role_for_branch(event.branch)`; the STAGING→"staging" / RELEASE→"production" mapping is the lone `_ENVIRONMENT_BY_ROLE` lookup.
  - `str(version)`, `github_url`, and `notes` are the exact values 11.3 already produced — no second `str(...)`, no second `report_notes`.
  - `summaries` keys are exactly `declared_languages` (the app's declared set); each is present in `notes` because `union` includes `declared_languages` and `report_notes` returns keys == langs. Values are coerced with `notes[lang] or ""`, mirroring the sibling channels (GitHub release body `router.py:88`, Telegram note `router.py:97`): `PivotLocalizer.report_notes` maps every language to `None` for an empty report (`localizer.py:84-85`), and the frozen `summaries: object` wire shape is strings — so a `None` note is sent as `""`, never `null`.
  - The `try/except` catches and logs an `entry` failure individually — the already-delivered GitHub release and Telegram are never rolled back, and the failure never aborts the background task.
  The whole leg runs inside 11.3's single `_run_isolated`/`background_tasks.add_task` task (`router.py:190-195`) — no second task is added, and `router.py`'s staging/release scheduling block is otherwise unchanged (it already threads `changelog_client`).

  Also update the `_deliver_release` docstring (`router.py:44-54`): its second paragraph states the changelog leg *"is dormant until the changelog app itself is wired"*, which Tasks 2–3 make false. Rewrite that paragraph to describe the now-active last leg — a mapped, reachable app receives a `ChangelogEntry` after the release and Telegram send — while preserving the still-true degrade behavior: when `changelog_client`/`base_url` is absent or the app is unreachable (at `config` or `entry`), the union stays the fixed-channel languages and an unreachable app never blocks the GitHub release or Telegram delivery.

### Phase 3: Tests

- [x] **Task 4: Align the test fake with the frozen contract and add entry-leg tests** (depends on Task 3)
  Files: `tests/ingestion/test_release_delivery.py`
  - Align `FakeChangelogClient` with the frozen `ChangelogClient` shape: `config(base_url) -> list[str]` (delete `FakeChangelogConfig`; return `self._languages` directly). Add an async `entry(self, base_url, payload)` that appends `(base_url, payload)` to a recorded `self.entries: list` (and can be made to raise for the unreachable-at-entry case, e.g. a separate `entry_raises` flag). Update the module docstring line describing the "`config(base_url) -> object with .languages`" shape to the `list[str]` shape. Keep the two existing changelog tests green: `test_union_includes_changelog_app_languages_when_reachable` (union still `{ru, en, de}`) and `test_unreachable_changelog_app_still_cuts_release_and_delivers` (config raising → no entry, release + Telegram still delivered).
  - Add: a **mapped, reachable** staging push whose app declares `["ru", "en", "de"]` → exactly one recorded `entry` with `environment == "staging"`, `version == str(VERSION)`, `github_url` equal to the release URL, and `summaries` keys == `{"ru", "en", "de"}` with each value the corresponding `notes[lang]`.
  - Add: a **release** (branch `main`) mapped push → recorded `entry` with `environment == "production"`.
  - Add: an **unmapped** repo (`changelog_base_url=None`, `changelog_client` present) → no `entry` recorded, while `github_release_client` and `delivery_service` still fired.
  - Add: **app unreachable at `entry`** (`entry` raises) → the release + Telegram were delivered and the raise is swallowed (the call to `_deliver_release` completes without propagating).
  - Add: **zero re-derivation** — when the channel fires, `FakeChangelogClient.config` was called exactly once and `FakeLocalizer.report_notes` exactly once (assert against the existing `report_notes_calls` / a `config` call counter).
  - A `None`-version back-merge posting no entry is already covered by `test_none_version_skips_release_and_delivery` (early return); no new case needed beyond confirming `entries == []` there if convenient.
