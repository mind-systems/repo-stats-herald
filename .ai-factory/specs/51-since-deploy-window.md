# 11.2.1 — SinceDeployWindow (red tests)

**Phase:** 11 — GitHub releases & versioning. Depends on 10.1.1 (the `ReportWindow` seam), Phase 3 (the mirror's tags). Adds the deploy-anchored window a release note is built over; the release-note impl (11.2.2) greens on it.

## Current state

`ReportWindow` (10.1.1) has one impl, `TimeWindow` (a day / a week). A release note is not time-boxed — it spans since the last deploy to an environment. Nothing resolves that range, and a naive "since the last `-rc`" rule silently re-narrates already-released work.

## Change

Add `SinceDeployWindow(environment)` implementing `ReportWindow.resolve(repo) -> (before, after)`: `after` = HEAD; `before` = the last **deploy tag** for the environment on the mirror.

- `master`/`main` (release) → the last **full release** tag.
- `staging` → the last **deploy tag of ANY type** — `max(last full release, last pre-release)`, NOT "the last `-rc`". After a full `v1.2.0`, the next staging window starts at `v1.2.0`, not the stale `v1.2.0-rc`.
- Tag selection is **semver-aware** — `v1.10.0 > v1.9.0`, never lexicographic and never by commit date; non-version tags are ignored.
- No deploy tag → `before` = the repo's start (root).

## Files & types

- new `src/changelog/windows/since_deploy.py` (`SinceDeployWindow`)

## Guards (red tests over a fixture mirror with known tags)

- **staging after a full release** — with tags `v1.2.0-rc` then `v1.2.0`, `SinceDeployWindow("staging").resolve` starts at `v1.2.0` (the plantable bug: starting at `v1.2.0-rc` and re-narrating the released set).
- **semver-aware** — with `v1.9.0` and `v1.10.0`, the base is `v1.10.0` (not `v1.9.0` by string order).
- **non-version tags ignored** — a `nightly`/`build-42` tag is not chosen as a base.
- **no tag** — a repo with no deploy tag → range from root, no crash.
- release env picks the last full release; staging picks `max(full, rc)`.

## Verification

- staging with `[…, v1.2.0-rc, v1.2.0]` → base `v1.2.0`; a further `-rc` after that → base the newer `-rc` (max wins).
- release env with `[v1.1.0, v1.2.0]` → base `v1.2.0`.
- `v1.10.0` beats `v1.9.0`; `nightly` ignored; empty → root.
