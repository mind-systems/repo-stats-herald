# Versioning

Herald assigns a version to every staging and release push and reflects it
consistently across the channels that carry a version: the GitHub release tag, the
Telegram header, and the internal changelog entry.

## Rules

| Trigger | Version | GitHub artifact |
|---------|---------|-----------------|
| Push to the default branch (`master`/`main`) | semver tag, e.g. `v1.2.0` | full release |
| Push to `staging` | same semver with a `-rc` suffix, e.g. `v1.2.0-rc` | pre-release |

Staging always mirrors the version the release will carry, marked as a release
candidate. The two describe the same change set at two stages of its life.

## Back-merge detection

A back-merge from the default branch into staging carries commits that are already
part of the released history. Herald detects this — the incoming commit SHAs are
already present on the default branch — and skips the version bump, so a back-merge
does not manufacture a spurious release candidate. Only genuinely new work on staging
advances the version.

## Where the version flows

Once assigned, the version is the same token everywhere it appears:

- the **GitHub release/pre-release** tag,
- the **Telegram** version header on the announcement,
- the `version` field of the **internal changelog entry** written to an integrated app
  (see [internal-protocol.md](internal-protocol.md)).

The increment step — whether a push advances the major, minor, or patch component — is
a configuration point rather than a fixed rule baked into delivery, and is resolved
alongside the rest of the delivery plan (see [configuration.md](configuration.md)).
