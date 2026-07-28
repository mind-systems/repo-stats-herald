# Plan Review: 11.2.1 — SinceDeployWindow (red tests)

**Plan:** `.ai-factory/plans/50-11-2-1-sincedeploywindow-red-tests.md`
**Governing spec:** `.ai-factory/specs/51-since-deploy-window.md` (ROADMAP line 11.2.1)
**Risk Level:** 🟢 Low

## Code Review Summary

**Files reviewed (ground truth):** `src/changelog/report.py`, `src/commits/collector.py`,
`src/versioning/versioner.py`, `src/routing/models.py`, `src/routing/resolver.py`,
`src/github/mirror.py`, `src/changelog/sections/__init__.py`,
`tests/versioning/test_versioner.py`, `tests/changelog/test_time_window.py`,
`tests/changelog/conftest.py`, plus the governing spec and ROADMAP.

The plan is accurate and closely grounded in the codebase. Every API it leans on was
verified against the actual source:

- `ReportWindow.resolve(self, repo: str) -> tuple[str, str]` and the "no `org_id` /
  never `mirror.ensure`" contract — matches `report.py:12-24` verbatim.
- `GitCommitCollector.list_tags(repo_path) -> tuple[str, ...]` (parse-agnostic) and
  `EMPTY_TREE_SHA` — match `collector.py:196-209, 23`.
- `Version.parse` returning `None` for non-version tags, `@total_ordering` with a full
  release ranking above its own `-rc`, and the `parsed = [(v, tag) for tag in ... if (v := Version.parse(tag)) is not None]`
  reuse shape — match `versioner.py:12-56, 104-106`.
- `bare = str(mirror.object_store_path(repo))` — matches `Versioner`/`TimeWindow` usage
  (`versioner.py:102`, `report.py:48`).
- `BranchRole` enum members — match `routing/models.py:5-8`.
- Import paths (`src.github.mirror`, `src.commits.collector`, `src.routing.models`,
  `src.versioning.versioner`, `src.changelog.report`) — all resolve.
- Test infrastructure: `asyncio_mode = "auto"` in `pyproject.toml` confirms async tests
  run without decorators; `tests/versioning/test_versioner.py` supplies exactly the
  `git_repo` / `FakeMirror` / `_commit` / `_tag` style the plan proposes to mirror.

The STAGING logic is correct: `max` over **all** parsed pairs yields `v1.2.0` when both
`v1.2.0-rc` and `v1.2.0` exist (full > own `-rc` at equal base) and yields a later
`v1.3.0-rc` once it appears — algebraically identical to `max(last full, last rc)`, as
the spec requires. The plan correctly forbids special-casing `-rc`.

### Context Gates

- **Architecture (`.ai-factory/ARCHITECTURE.md`):** PASS. `changelog` depending on
  `versioning`/`routing`/`commits`/`github` via their public classes (`Version`,
  `BranchRole`, `GitCommitCollector`, `RepoMirror`), injected through the constructor, is
  exactly the cross-feature rule at ARCHITECTURE.md:42 — and mirrors what `Versioner`
  itself already does. Concrete wiring is left to a composition root, not this class.
- **Rules (`.ai-factory/RULES.md`):** present; no violation observed (plan sets
  Logging: none, Docs: no, consistent with a red-tests-only task).
- **Roadmap:** PASS. Plan heading matches ROADMAP line 11.2.1; spec linkage present and
  followed to the leaf. 11.2.2 (the consumer) is the next `[ ]` line, consistent with
  "the release-note impl greens on it."
- **skill-context (`.ai-factory/skill-context/aif-review/SKILL.md`):** absent — no
  project-specific review overrides to apply.

### Findings

**1. `BranchRole.DEV` path is left undefined — latent unbound-variable / undefined behavior (Low)**
`Task 2` types the constructor param as `environment: BranchRole` (the full enum, which
includes `DEV`), and `resolve` describes exactly two branches: `RELEASE` → full-release
candidates, `STAGING` → all parsed pairs, then `max(candidates, ...)`. Nothing defines
what happens for `DEV`. An implementer following the plan literally
(`if role is RELEASE: candidates = ...; elif role is STAGING: candidates = ...`) leaves
`candidates` unbound on the `DEV` path → `NameError` at resolve time rather than a clear
error or defined range. This is reachable in principle: `role_for_branch`
(`src/routing/resolver.py:8-13`) returns `BranchRole.DEV` for any non-release/non-staging
branch, and the spec says the caller passes a role *already resolved via
`role_for_branch`*. The spec restricts the environment to `RELEASE`/`STAGING`, so this is
outside the guard set — but the fix lives entirely inside the new `since_deploy.py` this
task creates, so it is in scope. Recommend the plan pin the `else` explicitly (e.g. a
`raise ValueError(f"unsupported environment: {environment!r}")` documenting the
RELEASE/STAGING precondition, or an explicit statement that `DEV` is treated as `STAGING`).
A one-line guard test would also make the precondition observable.

**2. `Task 1` justification is loosely worded (Nit)**
Task 1 says "Add an empty package marker … Mirrors the existing `src/changelog/sections/`
sub-package layout." The instruction (create an empty `__init__.py`) is correct and
appropriate — but `src/changelog/sections/__init__.py` is *not* empty; it holds
`default_section_registry(...)`. The `windows` package needs no such registry yet, so an
empty marker is right; only the "mirrors sections layout" phrasing is inaccurate. No
change to the instruction needed — flagging only so the implementer isn't surprised into
copying a registry that shouldn't exist.

### Positive Notes

- The plan's "Codebase notes (ground truth to follow)" section is precise and matches the
  source line-for-line — including the subtle STAGING ordering rationale and the
  `Version` reuse shape lifted from `Versioner.next`.
- The invariant "never call `mirror.ensure`" is carried explicitly and echoed as a class
  docstring requirement, keeping the seam contract visible — faithful to `ReportWindow`'s
  own docstring.
- Returning the **original tag string** (not a re-rendered `str(Version)`) as `before`
  preserves the tag's exact spelling as a valid git ref — a correct, easy-to-miss detail.
- The guard test list covers every trap the spec pins, including the planted-bug
  staging-after-full-release case and the injected-collector spy that pins shared-primitive
  reuse (with a `FakeMirror` stub and no real git — appropriate for that one).
- Test-strategy reuse is well chosen: the `versioner` test helpers are the right template,
  and `changelog/conftest.py` (verified) offers no conflicting git fixtures to collide with.

## Deferred observations

- Affects: 11.2.2 (release-note impl) — the plan leaves `after = "HEAD"` as a literal ref
  rather than a resolved SHA (per spec, "`after` = HEAD"). This is correct for this task,
  but the consuming pipeline must ensure sections that receive `after` treat it as a live
  ref against the already-ensured bare store; if any downstream consumer expects a pinned
  SHA (as `TimeWindow` returns), that mismatch surfaces in 11.2.2, not here.

Overall the plan is implementation-ready. Address finding 1 (define the `DEV`/`else`
behavior) and the plan is solid.
