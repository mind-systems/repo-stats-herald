# Plan: 11.1 — Versioning + back-merge skip

## Context
Compute the semver version a staging/release push carries — first-ever `v0.1.0`, staging `-rc` bumps, default-branch promotion vs hotfix — while skipping back-merges that carry no staging-unique work, per `.ai-factory/specs/19-versioning.md` and `docs/behavior/delivery.md#versioning`.

## Settings
- Testing: yes (back-merge detection is a silent-failure surface; the spec mandates red tests — see Phase 3)
- Logging: minimal
- Docs: no (`docs/behavior/delivery.md#versioning` already governs this behavior; no doc change)

## Tasks

### Phase 1: Config + shared git primitives

- [x] **Task 1: Add `version_increment` to `Settings`**
  Files: `src/core/config.py`
  Add `version_increment: Literal["major", "minor", "patch"] = "patch"` to the `Settings` class (add `Literal` to the existing `from typing import ...` import). No custom validator — pydantic's `Literal` validation already makes an invalid value a startup error, which is the required behavior. This primitive is read once at the composition root and injected into `Versioner` (Task 4); features never read it directly.

- [x] **Task 2: Add `list_tags`, `is_ancestor`, `new_commits` to `GitCommitCollector`**
  Files: `src/commits/collector.py`
  Extend the existing class with three read-only git primitives, following the class's established idiom (`-C <repo_path>`, `--end-of-options` before user-supplied refs, `subprocess.run(..., check=False)` with a no-raise fallback, split-on-`splitlines()`-and-drop-blank). These are the single home for tag listing / ancestor checks / back-merge content:
  - `list_tags(repo_path: str) -> tuple[str, ...]` — `git tag`; return the raw tag strings verbatim (empty tuple on non-zero exit). Do NOT filter non-version tags here — semver parsing/filtering is the caller's job (`Version.parse`, Task 3). `list_tags` is also reused by `SinceDeployWindow` (11.2.1), so it must stay parse-agnostic.
  - `is_ancestor(repo_path: str, sha: str, ref: str) -> bool` — `git merge-base --is-ancestor <sha> <ref>` with `check=False`; return `result.returncode == 0` (exit 0 → `True`, any non-zero → `False`, never raises). `sha` may itself be a tag name/ref.
  - `new_commits(repo_path: str, before: str, after: str, exclude_ref: str) -> tuple[str, ...]` — `git rev-list <before>..<after> --no-merges --not <exclude_ref>` with `check=False` (empty tuple on non-zero exit); return the non-blank SHA lines. `--no-merges` drops the merge commit itself and `--not <exclude_ref>` drops anything already reachable from `exclude_ref`, so a fast-forward OR merge-commit back-merge that pulls the exclude ref down with no unique non-merge work yields an empty tuple. Mind argument order: git wants the range and the `--not <ref>` on the command line — pass `f"{before}..{after}"`, then `--no-merges`, then `--not`, then `exclude_ref` (place `exclude_ref` after `--end-of-options` per the class idiom).

### Phase 2: Versioning module

- [x] **Task 3: `Version` value object** (depends on Task 1)
  Files: `src/versioning/__init__.py` (new, empty package marker), `src/versioning/versioner.py` (new)
  Add a `Version` value object (frozen dataclass) holding `major`, `minor`, `patch` ints and a `prerelease: bool` flag (the `-rc` marker — a boolean, never an `-rc.N` counter).
  - `__str__` is the ONE canonical render path: `v{major}.{minor}.{patch}` for a full release, `v{major}.{minor}.{patch}-rc` when `prerelease` is `True`. No second formatting site anywhere — every consumer (11.3's `tag_name`, the Telegram header) calls `str(version)`.
  - `@classmethod parse(cls, tag: str) -> "Version | None"` — the shared semver parse both `Versioner` and `SinceDeployWindow` (11.2.1) use. Accept optional leading `v`, `MAJOR.MINOR.PATCH`, optional `-rc` suffix (no numeric counter); return `None` for any non-version tag (e.g. `nightly`, `build-42`, `v1.2` with a missing component) so callers filter by `is not None`.
  - Ordering must be semver-aware, not lexicographic (`v1.10.0 > v1.9.0`): order by the `(major, minor, patch)` tuple, and for an equal base rank a full release above its `-rc` (standard semver precedence). Implement via `functools.total_ordering` or explicit comparison so `max(...)` over a list of `Version` is correct.
  - Add a helper to bump one component and return a full (non-prerelease) `Version`, e.g. `bump(self, component: str) -> "Version"` — `major` → `(M+1, 0, 0)`, `minor` → `(M, m+1, 0)`, `patch` → `(M, m, p+1)`, always `prerelease=False`. Also provide a cheap way to derive the `-rc` form and the full form of a base (e.g. a `base` property or `replace`-style helpers) so `Versioner` composes results without re-formatting.

- [x] **Task 4: `Versioner` with `next(...)`** (depends on Task 2, Task 3)
  Files: `src/versioning/versioner.py`
  Add `Versioner` using constructor DI mirroring `src/episodic/backfill.py` / `src/knowledge/sync.py`: `__init__(self, mirror: RepoMirror, collector: GitCommitCollector, version_increment: str) -> None` — store all three; never construct a concrete `RepoMirror`/`GitCommitCollector`. Import `RepoMirror` from `src/github/mirror.py`, `GitCommitCollector` from `src/commits/collector.py`, and `BranchRole` from `src/routing/models.py`.
  `next(self, repo: str, role: BranchRole, before: str, after: str) -> Version | None`:
  - Resolve `bare = str(self._mirror.object_store_path(repo))` (the read-only bare store, never a worktree). Read `tags = self._collector.list_tags(bare)` and build the parsed set `[v for t in tags if (v := Version.parse(t)) is not None]`, keeping each parsed `Version` paired with its raw tag string (needed to pass the raw tag to `is_ancestor`). Take `role` as given — never compare `branch == "staging"`/`"master"` inline (role already came from `role_for_branch`, 9.1).
  - **`BranchRole.STAGING`:**
    - Back-merge guard FIRST: `exclude_ref = self._mirror.default_branch(repo)` (the default-branch name, e.g. `main`); if `self._collector.new_commits(bare, before, after, exclude_ref)` is empty → return `None` (a back-merge — fast-forward or merge-commit — brings no staging-unique non-merge work, so no bump and no spurious `-rc`).
    - No parseable version tag at all → return `v0.1.0-rc` directly (`Version(0, 1, 0, prerelease=True)`) — the repo's first version, NOT bumped from a synthetic `v0.0.0`.
    - Otherwise the bump basis is the semver-max over BOTH full and `-rc` parsed versions; bump the configured `version_increment` component off that max and append `-rc`. Every staging push advances (`v1.2.1-rc`, then `v1.2.2-rc`) — no `-rc.N`, no re-tagging.
  - **`BranchRole.RELEASE`** — full releases (`prerelease` False on the result):
    - Compute the last full release = semver-max over parsed full (`not prerelease`) versions, or `None` if none.
    - **Promotion:** among parsed `-rc` versions whose base is greater than the last full release (all of them when there is no full release), keep those whose raw tag is reachable from `after` (`self._collector.is_ancestor(bare, <raw rc tag>, after)`); if any, adopt the highest such candidate's base as a full release (drop `-rc`, no further bump) and return it.
    - **Hotfix:** no reachable `-rc` candidate but a full release tag exists → bump `version_increment` off the last full release and return the full version.
    - **First version:** neither a reachable candidate nor any full release tag (e.g. no version tag at all) → return `v0.1.0` full (`Version(0, 1, 0)`). This unifies the spec's "no version tag → hotfix cuts `v0.1.0`" case with the degenerate "only `-rc` tags, none reachable, no full release" case — both yield the first full version rather than bumping a synthetic `v0.0.0`. (Assumption: the spec's explicit hotfix branch presumes a full release exists; this fallback keeps `next` total and consistent with the no-tag rule for the case the spec leaves implicit.)
  - **`BranchRole.DEV`** — out of scope; callers (9.1/11.3) gate on `RELEASE`/`STAGING` only. Do not add a DEV path (let it fall through / raise `ValueError` is unnecessary — simply no branch handles it since it is never called; keep the method returning only via the two handled roles).

### Phase 3: Tests (mandated — back-merge is a silent-failure surface)

- [x] **Task 5: Collector primitive tests** (depends on Task 2)
  Files: `tests/commits/test_collector.py`
  Add tests for the three new primitives over a real throwaway repo (reuse the `git_repo` / `commit_at` fixtures and `_git` helper style in `tests/commits/conftest.py`; add local helpers for branching/merging/tagging as needed). Pin the back-merge check specifically on `new_commits`, not only via `Versioner`:
  - `list_tags` returns all tag names including non-version ones (parse-agnostic), and an empty tuple on a repo with no tags.
  - `is_ancestor` → `True` when `sha` is reachable from `ref`, `False` otherwise, and `False` (no raise) for an unknown ref.
  - `new_commits`: (1) a fast-forward back-merge where `before..after ⊆ default` → empty; (2) a merge-commit back-merge (default merged into staging via a real merge commit, no staging-unique non-merge commit) → empty (the merge commit dropped by `--no-merges`, its parents already reachable via `--not <default>`); (3) a genuinely new non-merge commit on staging → the introduced SHA(s).

- [x] **Task 6: `Versioner.next` tests** (depends on Task 4)
  Files: `tests/versioning/__init__.py` (new), `tests/versioning/test_versioner.py` (new)
  Drive `Versioner.next` over a fixture repo through a lightweight fake mirror (a small stub exposing `object_store_path(repo) -> Path` returning the fixture repo path and `default_branch(repo) -> str` returning the default branch name — `Versioner` calls nothing else on the mirror), a real `GitCommitCollector`, and an explicit `version_increment`. Cover the spec's Verification list:
  - No tags → first staging push → `v0.1.0-rc`; a default-branch push with no candidate behind it → `v0.1.0`.
  - Two successive staging pushes with no intervening release → `v1.2.1-rc` then `v1.2.2-rc` (each advances off the semver-max; parameterize the seed tag so the bump component matches `version_increment`).
  - Promotion: a default-branch push whose work already rode a reachable `-rc` candidate → that candidate's base with `-rc` dropped, no further bump.
  - Hotfix: a default-branch push with no reachable candidate and a full release tag present → bump off the last full release.
  - Back-merge round-trip (the mandated red case): a hotfix commit lands on the default branch and is released (a full tag, e.g. `v1.2.1`, points at it), then is back-merged into `staging` via a merge commit with no staging-unique non-merge work → the staging push's `next` returns `None`. Also assert the fast-forward back-merge → `None`.
  - Semver-aware selection: with `v1.9.0` and `v1.10.0` present, the bump basis is `v1.10.0`, not `v1.9.0` (never lexicographic).
