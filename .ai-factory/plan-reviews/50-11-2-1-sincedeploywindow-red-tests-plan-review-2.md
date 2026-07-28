# Plan Review 2: 11.2.1 — SinceDeployWindow (red tests)

**Plan:** `.ai-factory/plans/50-11-2-1-sincedeploywindow-red-tests.md`
**Governing spec:** `.ai-factory/specs/51-since-deploy-window.md` (ROADMAP line 11.2.1)
**Prior review:** `.ai-factory/plan-reviews/50-11-2-1-sincedeploywindow-red-tests-plan-review-1.md`

## Code Review Summary

**Files reviewed (ground truth):** `src/changelog/report.py`, `src/commits/collector.py`,
`src/versioning/versioner.py`, `src/routing/models.py`, `src/routing/resolver.py`,
`src/github/mirror.py`, `tests/versioning/test_versioner.py`,
`tests/changelog/test_time_window.py`, `tests/changelog/conftest.py`, `pyproject.toml`,
plus the governing spec, ROADMAP line 11.2.1/11.2.2, ARCHITECTURE.md, and RULES.md.
**Risk Level:** 🟢 Low

Every API and pattern the plan leans on was re-verified against source:

- `ReportWindow.resolve(self, repo: str) -> tuple[str, str]` and the "no `org_id` / never
  `mirror.ensure`" seam contract — matches `report.py:12-24` verbatim, including the class
  docstring the plan asks `SinceDeployWindow` to echo.
- `GitCommitCollector.list_tags(repo_path) -> tuple[str, ...]` (parse-agnostic, no-raise)
  and `EMPTY_TREE_SHA` — match `collector.py:196-209, 23`.
- `Version.parse` returning `None` for non-version tags, `@total_ordering`, and the
  `_sort_key` `(major, minor, patch, 0 if prerelease else 1)` that ranks a full release
  **above** its own `-rc` at an equal base — match `versioner.py:12-56`. This is exactly
  what makes the STAGING `max`-over-all-pairs rule collapse to `max(last full, last rc)`.
- The `parsed = [(v, tag) for tag in tags if (v := Version.parse(tag)) is not None]` reuse
  shape and `bare = str(mirror.object_store_path(repo))` — match `Versioner.next`
  (`versioner.py:102-106`) and `TimeWindow.resolve` (`report.py:48`) line-for-line.
- `BranchRole` members `RELEASE`/`STAGING`/`DEV` — match `routing/models.py:5-8`; and
  `role_for_branch` (`routing/resolver.py:7-13`) does return `DEV` for any
  non-release/non-staging branch, confirming the unsupported-environment path is reachable
  in principle.
- Import paths (`src.github.mirror`, `src.commits.collector`, `src.routing.models`,
  `src.versioning.versioner`, `src.changelog.report`) — all resolve.
- Test infra: `pyproject.toml:22` sets `asyncio_mode = "auto"`, so `async def test_...`
  functions run without a decorator; `tests/versioning/test_versioner.py` supplies the
  exact `git_repo` / `FakeMirror(object_store_path)` / `_commit` / `_tag` template the plan
  proposes to mirror; `tests/changelog/conftest.py` defines only `make_fake_section` /
  `counting_window` fixtures — no `git_repo`/`collector`/`FakeMirror` name collision with
  the new test file.

### Resolution of prior-review findings

- **Finding 1 (BranchRole.DEV / unbound `candidates`) — RESOLVED.** Task 2 (plan line 41)
  now mandates raising `ValueError(f"unsupported environment: ...")` at the top of
  `resolve` for any member other than `RELEASE`/`STAGING`, turning the precondition into a
  loud failure instead of a latent `NameError`. Task 3 (plan line 57) adds the matching
  guard test: `SinceDeployWindow(mirror, collector, BranchRole.DEV).resolve(repo)` raises
  `ValueError`. Correctly ordered before any tag read.
- **Finding 2 (Task 1 phrasing) — RESOLVED.** Task 1 (plan line 26) now states the
  `windows` package is left genuinely empty *unlike* `sections/__init__.py` which holds
  `default_section_registry` — the earlier misleading "mirrors sections layout" wording is
  gone.

### Logic re-verification (STAGING/RELEASE selection)

- STAGING with `{v1.2.0-rc, v1.2.0}`: sort keys `(1,2,0,0)` vs `(1,2,0,1)` → `max` is the
  full `v1.2.0`. Returns `"v1.2.0"`, never the stale `-rc`. ✅ (the planted-bug case)
- STAGING with a further `v1.3.0-rc`: `(1,3,0,0) > (1,2,0,1)` → `max` is `v1.3.0-rc`. ✅
- Semver: `v1.10.0` `(1,10,0,1)` > `v1.9.0` `(1,9,0,1)`, never lexicographic. ✅
- RELEASE with `{v1.2.0, v1.3.0-rc}`: `max` over non-prerelease pairs → `v1.2.0`. ✅
- Empty candidate set (empty repo, or RELEASE with only `-rc`) → `EMPTY_TREE_SHA`; the plan
  explicitly guards this before `max`, avoiding `max([])` on an empty sequence. ✅
- Returns the **original tag string** from the winning pair (a valid git ref preserving
  exact spelling), not a re-rendered `str(Version)`. ✅

### Context Gates

- **Architecture (`.ai-factory/ARCHITECTURE.md`):** PASS. `changelog` depending on
  `versioning` (`Version`), `routing` (`BranchRole`), `commits` (`GitCommitCollector`),
  and `github` (`RepoMirror`) — all public classes, `mirror`/`collector` injected via
  constructor, concrete wiring left to a composition root — is exactly the cross-feature
  rule at ARCHITECTURE.md:41-43, and mirrors what `Versioner` already does.
- **Rules (`.ai-factory/RULES.md`):** PASS. File is intentionally empty (no project
  counter-defaults); nothing to enforce.
- **Roadmap:** PASS. Plan heading matches ROADMAP line 11.2.1; the `Spec:` tag resolves to
  `.ai-factory/specs/51-since-deploy-window.md`, followed to its code leaves. 11.2.2 (the
  release-note impl that greens on this window) is the next `[ ]` line, consistent with the
  spec's "the release-note impl greens on it."
- **skill-context (`.ai-factory/skill-context/aif-review/SKILL.md`):** absent (no
  `skill-context/` directory) — no project-specific review overrides to apply.

### Critical Issues

None.

### Positive Notes

- The plan's "Codebase notes (ground truth to follow)" is precise and matches source
  line-for-line, including the subtle `Version` ordering rationale that makes the
  no-special-case-for-`-rc` STAGING rule correct.
- The "never call `mirror.ensure`" invariant is carried explicitly and echoed as a class
  docstring requirement, keeping the seam contract visible — faithful to `ReportWindow`'s
  own docstring.
- The guard-test list covers every trap the spec pins: the planted-bug
  staging-after-full-release case, the semver-ordering case, non-version-tag rejection, the
  no-tag→root case, the RELEASE-vs-STAGING mixed case, the injected-collector spy pinning
  shared-primitive reuse (correctly noted as needing no real git), and the new
  unsupported-environment guard.
- Minor precision note for the implementer (not a defect): the `ValueError` snippet at plan
  line 41 writes `{environment!r}`; inside `resolve` the value is the stored attribute, so
  render it as `self.environment`. Loud and self-correcting on first run — no plan change
  required.

## Deferred observations

- Affects: 11.2.2 (release-note impl) — the plan returns `after = "HEAD"` as a literal ref
  rather than a resolved SHA (correct per spec: "`after` = HEAD"). The consuming pipeline
  must treat `after` as a live ref against the already-ensured bare store; if any
  downstream section expects a pinned SHA (as `TimeWindow` returns), that mismatch surfaces
  in 11.2.2, not in this red-tests task. [dismissed]

The plan is implementation-ready: both prior-review findings are closed, every API and
ordering claim is verified against ground truth, and the guard set fully covers the spec's
pinned traps.

PLAN_REVIEW_PASS
