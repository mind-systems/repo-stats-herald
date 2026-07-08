# 12.2 — Changelog channel wiring

**Phase:** 12 — Internal protocol (changelog channel). Depends on 12.1 (the client) and 11.3 (the resolved language union, the built notes, and the `github_url`). Closes the phase: the changelog channel fires for a mapped repo, and the protocol is ready for any app to integrate.

## Current state

After 12.1 Herald can speak the changelog protocol, but nothing invokes it on a push. The resolver surfaces the changelog target as `plan.changelog_base_url` (11.3 already reads it when resolving the language union), but nothing posts a changelog entry yet. Task 11.3's release-delivery wiring already resolves the required-language union — including this app's declared languages via `ChangelogClient.config`, called once as part of that union — and builds `notes: dict[lang, str]` (11.2) covering it.

## Change

Activate the changelog channel on a staging/release push to a mapped repo, reusing 11.3's already-resolved languages and notes.

- On a `staging`/`release` push to a repo with `plan.changelog_base_url` set, with a version (11.1 ≠ `None`) **and where 11.3's union resolution found the app available** (its `config` succeeded): reuse the app's declared languages and `notes` (already built by 11.3) — **no second `config` call, and no rebuilding of the notes** (it reuses the `report_notes` result 11.3 already produced). If 11.3 marked the app unavailable, the changelog channel is skipped for this push.
- `ChangelogClient.entry(plan.changelog_base_url, { version, environment: staging→"staging" / default→"production", summaries: { lang: notes[lang] for lang in declared_languages }, github_url (from 11.3's release) })`.
- The `entry` call runs **after** the GitHub release and the Telegram send (it needs the release `github_url`), and its failure is **caught and logged** — the already-delivered release and Telegram are never rolled back.
- Wire this into the staging/release delivery path, alongside the GitHub release and the version-headed Telegram (11.3).

## Files & types

- edit `src/delivery/service.py` (activate the changelog channel for a mapped repo)
- edit `src/ingestion/router.py` (staging/release path invokes it)

## Guards

- Only repos with `plan.changelog_base_url` set activate the channel; an unmapped repo is skipped (Telegram and the GitHub release still fire).
- `environment` derives from the branch role (staging → `staging`, default → `production`).
- **The entry's `summaries` carries exactly the app's declared languages** — an app declaring a language beyond RU/EN is served with no new mechanism; the localizer (8.2) already generates it.
- **No second `config` call and no re-build of the notes** — reuses the `report_notes` result 11.3's union resolution already produced.
- A `None` version (11.1 back-merge/skip) delivers no entry.
- The app's endpoint being unavailable (at `config` in 11.3, or at `entry` here) is caught and logged — the GitHub release and Telegram, which fire first, are unaffected. This is the ROADMAP Phase-12 invariant made mechanical.
- **Zero re-derivation** — firing the changelog channel makes **no** additional `ChangelogClient.config` call and **no** additional `report_notes` build; it consumes the literal declared-languages and `notes` object 11.3 produced. Mandatory test over mocked `ChangelogClient`/the 11.3-produced notes: `config` and `report_notes` are called zero extra times when the channel fires.

## Verification

- Against a **stub** app mapped in `repo_apps` declaring `["ru", "en", "de"]`: a staging push → the stub receives an `entry` with `environment=staging`, the version, `summaries` covering all three declared languages, and the `github_url`.
- An unmapped repo's staging push → no entry posted; Telegram and the GitHub release still deliver.
- A back-merge push → no entry.
- A mapped repo whose app is unreachable at `entry` time → the GitHub release + Telegram were already delivered; `entry` raises, is logged, and does not fail the delivery step.
- Firing the changelog channel triggers no second `config`/`report_notes` call.
