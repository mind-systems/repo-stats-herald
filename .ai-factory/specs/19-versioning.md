# 11.1 — Versioning + back-merge skip

**Phase:** 11 — GitHub releases & versioning. First task. Assigns the version a staging/release push carries.

## Current state

The delivery plan (9.1) knows the branch role and the `is_release`/`is_prerelease` flags but no version. Nothing computes a semver, and a back-merge from the default branch into staging would manufacture a spurious release candidate. The mirror (Phase 3) holds the repo's tags and history.

## Change

Compute the version for a staging/release push, skipping back-merges.

- Extend `src/core/config.py` `Settings` with `version_increment: str` (default `patch`).
- `src/versioning/versioner.py`:
  - `Version` — semver + optional `-rc` suffix; renders `v1.2.0` / `v1.2.0-rc`.
  - `Versioner.next(repo: str, branch: str, before: str, after: str) -> Version | None`:
    - read the last release tag on the mirror (`git tag` / `git describe --tags`); the next version bumps the configured component (`version_increment`, default `patch`); the increment policy is a configuration point (richer policies — conventional commits, manual — are a later extension).
    - `master`/`main` → the full version (`v1.2.0`); `staging` → the same version with `-rc`.
    - **back-merge** — if the push's new commits (`before..after`) are already reachable from the default branch (their SHAs present there), return `None` — no bump.

## Files & types

- edit `src/core/config.py` (`version_increment`)
- new `src/versioning/__init__.py`, `src/versioning/versioner.py` (`Version`, `Versioner`)

## Guards

- Reads the mirror (tags, history) — reproducible, no network.
- Back-merge (SHAs already on the default branch) → `None`, never a spurious `-rc`.
- **Back-merge detection is a silent-failure surface** — a wrong SHA-reachability check silently manufactures a spurious `-rc` or skips a real release. Mandatory red test over a fixture mirror: commits already reachable from the default branch (`before..after` ⊆ default) → `None`; genuinely new commits → a version. Pin the reachability check specifically, not only input/output pairs.
- **Last-tag selection is semver-aware** — `v1.10.0 > v1.9.0`, never lexicographic; non-version tags ignored (same discipline as `SinceDeployWindow`, 11.2.1).
- Staging mirrors the release version with `-rc` — the two describe the same change set.
- Increment component from `Settings`, not hardcoded.

## Verification

- A staging push with new work → `v1.2.0-rc`; a default-branch push → `v1.2.0`.
- A back-merge from the default branch into staging → `None` (no version).
- The staging `-rc` matches the version its eventual release will carry.
- A push whose new commits are all already on the default branch → `None` (reachability pinned).
- With tags `v1.9.0`, `v1.10.0` present, the base bump is off `v1.10.0`.
