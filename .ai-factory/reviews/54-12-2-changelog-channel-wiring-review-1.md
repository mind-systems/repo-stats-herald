# Code Review: 12.2 — Changelog channel wiring

**Files reviewed (in full):** `src/ingestion/router.py`, `src/main.py`, `tests/ingestion/test_release_delivery.py`, cross-checked against `src/delivery/changelog_client.py`, `src/routing/models.py`, `src/reasoning/localizer.py`, the plan, and spec `23-changelog-channel-wiring.md`.
**Risk level:** 🟢 Low

The change activates the changelog channel exactly as planned. All three planned edits landed and are internally consistent; the full test suite for the fan-out (12 cases) and the changelog client (7 cases) passes, `import src.main` / `import src.ingestion.router` succeed.

## Correctness verification

- **Client registered at the composition root** (`main.py:13,115`) — `app.state.changelog_client = ChangelogClient()` is co-located inside the `github_app`-gated block with the other release-delivery collaborators, so it exists precisely when the fan-out can run. Deviation #2 from the plan is resolved.
- **Contract-drift bug fixed** (`router.py:78-82`) — `config` is now consumed as `list[str]` (matching the frozen `ChangelogClient.config(base_url) -> list[str]`, `changelog_client.py:27`) and captured in `declared_languages`. The former `config.languages` AttributeError path that silently forced `app_available=False` is gone. The test fake was aligned to return `list[str]` (`test_release_delivery.py:124-128`), removing the fiction that masked the bug. Deviation #3 resolved.
- **Entry leg placement and ordering** (`router.py:103-117`) — posted after the GitHub release (`:90`) and the Telegram send (`:101`), inside the same `_deliver_release` body that runs as 11.3's single `_run_isolated` task. Gated on `app_available`, which encodes "mapped (`base_url` set) AND `config` succeeded", so an unmapped repo or a `config` failure never reaches `entry`.
- **`None` version** returns early at `:68-71` before any release/entry work — a back-merge posts nothing. Confirmed by `test_none_version_skips_release_and_delivery`.
- **Failure isolation** — the `entry` call is wrapped in its own `try/except … logger.exception` (`:104-117`); a raise there leaves the already-delivered release and Telegram untouched and does not abort the task. Confirmed by `test_app_unreachable_at_entry_still_delivered_and_raise_swallowed`.
- **Zero re-derivation** — `str(version)`, `github_url`, `role`, and `notes` are reused; the environment mapping is the single module-level `_ENVIRONMENT_BY_ROLE` (`router.py:22`, STAGING→"staging" / RELEASE→"production") with no second `role_for_branch`, no second `config`, no second `report_notes`. Asserted by `test_changelog_entry_reuses_config_and_report_notes_without_re_deriving` (config called once, report_notes called once).
- **`summaries` values are strings** — `{lang: notes[lang] or "" for lang in declared_languages}` coerces the `None` an empty report yields (`PivotLocalizer.report_notes` → `localizer.py:84-85`) to `""`, matching the sibling GitHub/Telegram channels and honoring the frozen `summaries: object` (strings) shape — never `null` on the wire.
- **No `KeyError` on `notes[lang]`** — `union |= set(declared_languages)` guarantees `report_notes` (keys == `langs`) covers every declared language; and were a key ever absent, the `try/except` degrades safely.

## Runtime / integration checks
- No migration, schema, or config surface touched; `ChangelogClient()` uses its default timeout, no new setting required.
- `changelog_client.entry(base_url, ChangelogEntry(...))` matches the real signature (`changelog_client.py:33`); `ChangelogEntry` field order/types align.
- The router's scheduling block (`router.py` staging/release gate) was already threading `changelog_client` via `getattr(state, ..., None)` from 11.3 and needed no change — consistent with the diff.

## Findings
None.

REVIEW_PASS
