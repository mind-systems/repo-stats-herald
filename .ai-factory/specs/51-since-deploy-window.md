# 11.2.1 — SinceDeployWindow (red tests)

**Phase:** 11 — GitHub releases & versioning. Depends on 10.1.1 (the `ReportWindow` seam), 9.1 (`BranchRole`), Phase 3 (the mirror's tags), 11.1 (the shared `GitCommitCollector` tag primitive). Adds the deploy-anchored window a release note is built over; the release-note impl (11.2.2) greens on it.

## Current state

`ReportWindow` (10.1.1) has one impl, `TimeWindow` (a day / a week). A release note is not time-boxed — it spans since the last deploy to an environment. Nothing resolves that range, and a naive "since the last `-rc`" rule silently re-narrates already-released work. 11.1 adds `GitCommitCollector.list_tags` — the semver-aware, non-version-tags-ignored tag read this task must reuse rather than re-implement.

## Change

Add `SinceDeployWindow(environment: BranchRole)` implementing `ReportWindow.resolve(repo) -> (before, after)`: `after` = HEAD; `before` = the last **deploy tag** for the environment on the mirror.

- Constructor DI: `SinceDeployWindow.__init__(self, mirror: RepoMirror, collector: GitCommitCollector, environment: BranchRole) -> None` — `environment` is `src/routing/models.py`'s `BranchRole` (9.1: `RELEASE`/`STAGING`), never a parallel string enum; the caller passes the role already resolved via `role_for_branch` (9.1), never a raw branch string. `resolve(repo)` reads tags through the injected `collector.list_tags(bare)` where `bare = str(mirror.object_store_path(repo))` — the SAME shared primitive `Versioner` (11.1) uses, so the two never disagree on what counts as a version tag or how they order.
- `environment == BranchRole.RELEASE` → the last **full release** tag.
- `environment == BranchRole.STAGING` → the last **deploy tag of ANY type** — `max(last full release, last pre-release)`, NOT "the last `-rc`". After a full `v1.2.0`, the next staging window starts at `v1.2.0`, not the stale `v1.2.0-rc`. (Unchanged by 11.1's promotion/hotfix model — the window's job is only "since the last thing shipped to this environment," not version arithmetic.)
- Tag selection is **semver-aware** — `v1.10.0 > v1.9.0`, never lexicographic and never by commit date; non-version tags are ignored (via `list_tags`'s parse, 11.1).
- No deploy tag → `before` = the repo's start (root, `GitCommitCollector.EMPTY_TREE_SHA`).
- **Invariant:** `resolve(repo)` reads the already-ensured bare object store; it never calls `mirror.ensure(repo, org_id)` itself — `ReportWindow.resolve(repo)` (10.1.1) carries no `org_id`, so the caller (the report-build pipeline, 10.2/11.2.2) MUST have run `mirror.ensure(repo, org_id)` before invoking `Report.build`/`window.resolve`. A `SinceDeployWindow` constructed against an un-ensured repo has undefined behavior — not this task's guard to add, since it has no `org_id` to `ensure` with.

## Files & types

- new `src/changelog/windows/since_deploy.py` (`SinceDeployWindow`)

## Guards (red tests over a fixture mirror with known tags)

- **staging after a full release** — with tags `v1.2.0-rc` then `v1.2.0`, `SinceDeployWindow(BranchRole.STAGING).resolve` starts at `v1.2.0` (the plantable bug: starting at `v1.2.0-rc` and re-narrating the released set).
- **semver-aware** — with `v1.9.0` and `v1.10.0`, the base is `v1.10.0` (not `v1.9.0` by string order).
- **non-version tags ignored** — a `nightly`/`build-42` tag is not chosen as a base.
- **no tag** — a repo with no deploy tag → range from root, no crash.
- `environment == BranchRole.RELEASE` picks the last full release; `environment == BranchRole.STAGING` picks `max(full, rc)`.
- Tag reads go through the injected `collector.list_tags` — a red test with a mocked collector pins that `SinceDeployWindow` calls it rather than shelling its own `git tag`.

## Verification

- staging with `[…, v1.2.0-rc, v1.2.0]` → base `v1.2.0`; a further `-rc` after that → base the newer `-rc` (max wins).
- release env with `[v1.1.0, v1.2.0]` → base `v1.2.0`.
- `v1.10.0` beats `v1.9.0`; `nightly` ignored; empty → root.
