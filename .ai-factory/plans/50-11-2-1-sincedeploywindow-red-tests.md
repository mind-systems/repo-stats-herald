# Plan: 11.2.1 — SinceDeployWindow (red tests)

## Context
Add `SinceDeployWindow`, a `ReportWindow` impl that anchors a release note's `before` to the last deploy tag for an environment (`BranchRole`), reusing the shared `GitCommitCollector.list_tags` primitive, and the red/guard tests that pin its trap cases (staging-after-full-release, semver ordering, non-version tags, no-tag root, shared-primitive reuse).

## Settings
- Testing: yes
- Logging: none
- Docs: no

## Codebase notes (ground truth to follow)

- `ReportWindow` (ABC) and `TimeWindow` live in `src/changelog/report.py`. `resolve` is declared `async def resolve(self, repo: str) -> tuple[str, str]` and returns `(before, after)`. Its docstring already states the contract this task depends on: `resolve` carries no `org_id`, never calls `mirror.ensure`, and reads an already-ensured bare mirror.
- `BranchRole` is `src/routing/models.py` — `Enum` with `RELEASE = "release"`, `STAGING = "staging"`, `DEV = "dev"`. Use this enum directly; never a parallel string enum.
- The shared tag primitive is `GitCommitCollector.list_tags(repo_path) -> tuple[str, ...]` (`src/commits/collector.py`): raw `git tag` output, parse-agnostic (non-version tags NOT filtered here). `EMPTY_TREE_SHA` is exported from the same module (the root sentinel).
- Semver parsing/ordering is `Version` in `src/versioning/versioner.py`: `Version.parse(tag) -> Version | None` (returns `None` for `nightly`/`build-42`/malformed), and `Version` is `@total_ordering` with a full release ranking **above** its own `-rc` at an equal base, and semver-aware across bases (`v1.10.0 > v1.9.0`). `Versioner.next` already shows the exact reuse shape to mirror: `parsed = [(version, tag) for tag in collector.list_tags(bare) if (version := Version.parse(tag)) is not None]`, then `max(...)` over that. `Version` is imported from `src.versioning.versioner` — depending on the `versioning` feature's public value object is the intended cross-feature dependency (a feature depends on another feature's public class, not its internals).
- The bare path is read as `bare = str(mirror.object_store_path(repo))` — the identical call `Versioner` and `TimeWindow` use.
- Test patterns: `tests/versioning/test_versioner.py` shows the throwaway-git-repo + `FakeMirror` (exposing `object_store_path`) style; `tests/changelog/test_time_window.py` shows the async-test + `RepoMirror`/`mirror_for` fixture style. Either mirror shape works — a light `FakeMirror` exposing only `object_store_path` is sufficient here (this task never touches `ensure`/`default_branch`). Tests are async (`async def test_...`); the suite already runs them (see `test_time_window.py`).

## Tasks

### Phase 1: SinceDeployWindow

- [x] **Task 1: Create the `windows` sub-package**
  Files: `src/changelog/windows/__init__.py`
  Add an empty package marker so `src/changelog/windows/` is importable. (Note: leave it genuinely empty — unlike `src/changelog/sections/__init__.py`, which holds `default_section_registry`, `windows` needs no registry yet.)

- [x] **Task 2: Implement `SinceDeployWindow`**
  Files: `src/changelog/windows/since_deploy.py`
  Implement a `ReportWindow` subclass with plain constructor DI (match `Versioner`'s style, not `TimeWindow`'s frozen-dataclass equality — no equality contract is required here):
  - `def __init__(self, mirror: RepoMirror, collector: GitCommitCollector, environment: BranchRole) -> None` — store all three. Import `RepoMirror` from `src.github.mirror`, `GitCommitCollector` and `EMPTY_TREE_SHA` from `src.commits.collector`, `BranchRole` from `src.routing.models`, `Version` from `src.versioning.versioner`, and `ReportWindow` from `src.changelog.report`.
  - `async def resolve(self, repo: str) -> tuple[str, str]`:
    - `bare = str(self.mirror.object_store_path(repo))`.
    - Read tags via the **injected** collector: `tags = self.collector.list_tags(bare)`. Never shell a private `git tag` — the whole point is that `SinceDeployWindow` and `Versioner` agree on what counts as a version tag and how they order, by sharing this one primitive.
    - Build `parsed: list[tuple[Version, str]] = [(v, tag) for tag in tags if (v := Version.parse(tag)) is not None]` — this drops non-version tags (`nightly`, `build-42`) via `Version.parse` returning `None`.
    - Select the base tag by environment, using `Version`'s ordering (never lexicographic, never by commit date):
      - `BranchRole.RELEASE` → the last **full** release: `max` over pairs where `not version.prerelease`.
      - `BranchRole.STAGING` → the last deploy tag of **any** type: `max` over **all** `parsed` pairs. Because `Version` ranks a full release above its own `-rc` at an equal base, `max` over all pairs yields `v1.2.0` when both `v1.2.0-rc` and `v1.2.0` exist, and yields a later `v1.3.0-rc` once it appears — i.e. exactly `max(last full, last pre-release)`, NOT "the last `-rc`". Do not special-case `-rc`; let the ordering do the work.
      - Select by `max(candidates, key=lambda pair: pair[0])` and return the **original tag string** from the winning pair as `before` (a valid git ref; preserves the tag's exact spelling, e.g. an optional leading `v`).
    - No candidate (empty repo, or RELEASE env with only `-rc` tags and no full release) → `before = EMPTY_TREE_SHA`.
    - **Environment is `RELEASE` or `STAGING` only.** Branch the candidate selection on exactly those two members; for any other value (notably `BranchRole.DEV`, which `role_for_branch` returns for non-release/non-staging branches) `raise ValueError(f"unsupported environment: {environment!r}")` at the top of `resolve` rather than leaving a `candidates` variable unbound. This makes the spec's RELEASE/STAGING precondition an explicit, loud failure instead of a latent `NameError`.
    - `after = "HEAD"` per the spec (the mirror's current tip). Return `(before, after)`.
    - **Invariant to preserve:** do NOT call `self.mirror.ensure(...)` anywhere — `resolve(repo)` has no `org_id` and reads the already-ensured bare store. Add a class docstring stating this (behavior, not code) so the contract is visible at the seam, echoing `ReportWindow`'s own docstring.

### Phase 2: Red / guard tests

- [x] **Task 3: Guard tests over a fixture mirror with known tags** (depends on Task 2)
  Files: `tests/changelog/test_since_deploy_window.py`
  Async tests over a throwaway git repo with planted tags, driving `SinceDeployWindow.resolve`. Reuse the `tests/versioning/test_versioner.py` helpers' style: a `git_repo` fixture (`git init -b main`), `_commit`/`_tag` helpers, a `FakeMirror` exposing `object_store_path(repo) -> Path`, and a real `GitCommitCollector`. Assert on the returned `before` (the base tag string or `EMPTY_TREE_SHA`). Cover every guard the spec pins:
  - **staging after a full release** — tags `v1.2.0-rc` then `v1.2.0`; `SinceDeployWindow(mirror, collector, BranchRole.STAGING).resolve(repo)` → `before == "v1.2.0"` (the planted-bug case: must NOT be `v1.2.0-rc`, which would re-narrate the released set).
  - **staging, further `-rc` after the full release** — additionally tag `v1.3.0-rc`; STAGING → `before == "v1.3.0-rc"` (max wins).
  - **semver-aware** — tags `v1.9.0` and `v1.10.0`; base is `v1.10.0`, never `v1.9.0` by string order.
  - **non-version tags ignored** — a `nightly` / `build-42` tag alongside a real version tag is never chosen as the base.
  - **no tag → root** — a repo with no version tag: STAGING (and RELEASE) → `before == EMPTY_TREE_SHA`, no crash.
  - **release picks the last full release** — tags `v1.1.0` and `v1.2.0`; `BranchRole.RELEASE` → `before == "v1.2.0"`. Add a mixed case (`v1.2.0` full plus a higher `v1.3.0-rc`): RELEASE still picks `v1.2.0` (ignores the `-rc`), while STAGING picks `v1.3.0-rc`.
  - **goes through the injected collector** — construct `SinceDeployWindow` with a spy/stub collector whose `list_tags` returns a fixed tuple (and records that it was called); assert `resolve` selected the base from that returned tuple and that `list_tags` was invoked, pinning that the window reuses the shared primitive rather than shelling its own `git tag`. (Stub `object_store_path` via a `FakeMirror`; no real git needed for this one.)
  - **unsupported environment raises** — `SinceDeployWindow(mirror, collector, BranchRole.DEV).resolve(repo)` raises `ValueError`, making the RELEASE/STAGING precondition observable rather than a silent `NameError`.
