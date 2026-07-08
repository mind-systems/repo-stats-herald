# 11.3 — GitHub release + version header

**Phase:** 11 — GitHub releases & versioning. Depends on 11.1 (version), 11.2 (the note builder), 12.1 (a mapped app's declared languages, when one exists), Phase 3 (`GitHubAppAuth`), Phase 9 (Telegram delivery). Closes the phase: the version and note reach the release channels.

## Current state

After 11.1–11.2 Herald can build per-language notes for a staging/release push, but nothing resolves *which* languages are required, cuts a GitHub release, or adds the version header to the Telegram message. Phase 9's `DeliveryService` is transport-only (no per-push send); reports fire it on a cadence. The GitHub-release channel does not exist yet, and nothing resolves the required-language union or heads the Telegram message with a version. Both the Telegram and GitHub-release languages are configured defaults (RU, EN respectively, per `docs/spec/delivery.md`), not literals to be hardcoded here.

## Change

Resolve the required-language union once, build the notes once, then publish the GitHub release and head the Telegram message — each from its own language in the same result.

- Extend `DeliveryPlan` (9.1/9.3) with `github_release_language: str` (default `"en"`), mirroring the existing `language` field (Telegram, default `"ru"`) — both configured, never literals.
- On a `staging`/`release` push with a version (11.1 ≠ `None`): resolve the **required-language union** — `{plan.language, plan.github_release_language}` plus, when `plan.changelog_base_url` is set (resolved by 12.1), that app's declared languages via `ChangelogClient.config(plan.changelog_base_url)` (12.1). **`config` is failure-isolated**: if it raises (app unreachable), the app is dropped from this delivery — the union stays the fixed-channel languages, and the changelog channel is skipped (12.2), while the GitHub release and Telegram still fire. The resolution yields both the union and the app's declared languages (or a not-available marker the 12.2 wiring reads).
- `Localizer.report_notes(release_report(repo, org_id, branch), repo, org_id, union)` (11.2.2 + 10.3) **once** — one resolution and one set of notes feeding every release channel.
- `src/delivery/github_release.py` — `GitHubReleaseClient.create(repo: str, version: Version, body: str, prerelease: bool)`: with the installation token from `GitHubAppAuth` (Phase 3), `POST /repos/{repo}/releases` (`tag_name` = the version, `body` = `notes[plan.github_release_language]`, `prerelease` = true for `staging`, false for the default branch). Tag creation is implicit in the release call (`contents: write`).
- Extend `DeliveryService` (9.3): for a `staging`/`release` push, prepend the version header (`v1.2.0-rc` / `v1.2.0`) to `notes[plan.language]` (the Telegram message).
- Wire into ingestion: on a `staging`/`release` push, resolve the union → build the notes once (`report_notes`, 11.2.2 + 10.3) → create the release (`notes[plan.github_release_language]`) → deliver the version-headed Telegram (`notes[plan.language]`).

## Files & types

- new `src/delivery/github_release.py` (`GitHubReleaseClient`)
- edit `src/routing/models.py` (`DeliveryPlan.github_release_language`)
- edit `src/delivery/service.py` (version header on staging/release Telegram, keyed by `plan.language`)
- edit `src/ingestion/router.py` (staging/release path: resolve union → notes once → release + headed Telegram)

## Guards

- **One `report_notes` call per push** — feeds every release channel; no per-channel re-resolution.
- Channel languages come from the delivery plan / config (`plan.language`, `plan.github_release_language`) — never literals in this task's code.
- The release is created once per version; a `None` version (11.1 back-merge/skip) cuts nothing.
- `staging` → pre-release, default branch → full release.
- Release creation via the installation token; API errors raise.
- **Mandatory test over mocked `report_notes`/`GitHubReleaseClient.create`/`DeliveryService.deliver`:** exactly one `report_notes` call per push, feeding both the release body and the Telegram header from its result; the union passed to it equals `{plan.language, plan.github_release_language}` ∪ the mapped app's declared languages (when one exists); a `None` version → `report_notes`/`create` not called and the Telegram send carries no version header.
- **An unreachable app never blocks the other channels** (ROADMAP Phase-12 invariant) — a `ChangelogClient.config` failure during union resolution is caught, degrades the union to the fixed-channel languages, and marks the changelog channel unavailable; the release and Telegram are unaffected. Mandatory test (mocked `ChangelogClient.config` raising): the release is cut and the version-headed Telegram delivered; the union passed to `report_notes` is exactly `{plan.language, plan.github_release_language}`; the changelog channel is marked unavailable.

## Verification

- A `staging` push → a GitHub pre-release tagged `v1.2.0-rc` with the body in `plan.github_release_language`, plus a Telegram message headed `v1.2.0-rc` with the note in `plan.language` — both drawn from one `report_notes` call.
- A repo mapped to a changelog app declaring a third language → that language is present in the same `notes` result, at no extra resolution cost.
- A default-branch push → a full GitHub release `v1.2.0`.
- A back-merge (11.1 → `None`) → no release, and the Telegram message carries no version header.
- A mapped repo whose app is unreachable at `config` time → GitHub release + Telegram still delivered; union = the fixed-channel languages; changelog skipped, no crash.
