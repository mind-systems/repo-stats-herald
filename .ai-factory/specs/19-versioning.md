# 11.1 — Versioning + back-merge skip

**Phase:** 11 — GitHub releases & versioning. First task. Assigns the version a staging/release push carries.

## Current state

The delivery plan (9.1) knows the branch role and the `is_release`/`is_prerelease` flags but no version. Nothing computes a semver, and a back-merge from the default branch into staging would manufacture a spurious release candidate. The mirror (Phase 3) holds the repo's tags and history; `src/commits/collector.py`'s `GitCommitCollector` is the sole class shelling git subprocess calls today (idiom: `-C <repo_path>`, `--end-of-options`, `check=False`), and no tag-listing, ancestor-check, or content-based-back-merge primitive exists yet on it.

Version derivation assumes `staging` and the default branch keep a **preserved, append-only history**: no squash-merge, rebase, amend, or force-push on those branches; merges into them are real merges or fast-forwards (Herald relies on the repository's branch protection for this — see `docs/behavior/delivery.md#versioning`, "Preserved history on the release branches"). Under that precondition, a promoted change's commits reach the default branch intact, so `-rc`-tag reachability soundly tells a promotion from a hotfix (no product-decision fork remains here).

## Change

Compute the version for a staging/release push, skipping back-merges, per `docs/behavior/delivery.md#versioning`.

- Extend `src/core/config.py` `Settings` with `version_increment: Literal["major", "minor", "patch"]` (default `"patch"`) — an invalid value is a startup error (pydantic validation), not a silent no-op.
- Extend `src/commits/collector.py`'s `GitCommitCollector` with the shared git primitives this task (and `SinceDeployWindow`, 11.2.1, for `list_tags`) need, so semver parsing/ordering and back-merge logic each live in exactly one place:
  - `list_tags(repo_path: str) -> tuple[str, ...]` — `git tag`, non-version tags (`nightly`, `build-42`, …) filtered out by the caller's semver parse, not here.
  - `is_ancestor(repo_path: str, sha: str, ref: str) -> bool` — `git merge-base --is-ancestor <sha> <ref>` (`check=False`; exit code 0 → `True`, non-zero → `False`, never raises). Used for promotion-candidate reachability, NOT back-merge detection (see below).
  - `new_commits(repo_path: str, before: str, after: str, exclude_ref: str) -> tuple[str, ...]` — `git rev-list <before>..<after> --no-merges --not <exclude_ref>` (`check=False`, empty tuple on failure): the non-merge commits the push introduces that are not already reachable from `exclude_ref`. A back-merge (fast-forward OR via a merge commit) yields an empty tuple — the merge commit itself is excluded by `--no-merges`, so a merge that pulls the default branch down with no staging-unique work correctly reads as empty.
- `src/versioning/versioner.py`:
  - `Version` — semver + optional `-rc` suffix; renders through ONE canonical entry point (`__str__`) → `v1.2.0` / `v1.2.0-rc` (never `-rc.N`). Every consumer (11.3's `tag_name`, the Telegram header) calls `str(version)` — no independent formatting.
  - `Versioner.__init__(self, mirror: RepoMirror, collector: GitCommitCollector, version_increment: str) -> None` — constructor DI mirroring `src/episodic/backfill.py`'s and `src/knowledge/sync.py`'s `mirror: RepoMirror` injection; tags/history are read via `bare = str(mirror.object_store_path(repo))` (the bare, read-only store — never a worktree) passed into the injected `collector`'s new primitives.
  - `Versioner.next(self, repo: str, role: BranchRole, before: str, after: str) -> Version | None` — takes the already-classified `BranchRole` (`src/routing/models.py`, resolved via `role_for_branch`, 9.1); never compares `branch == "master"`/`"staging"` inline. Behavior per `docs/behavior/delivery.md#versioning`:
    - **back-merge** — `collector.new_commits(bare, before, after, default_branch_tip)` empty → `None`, no bump (default-branch tip read via `mirror.default_branch(repo)`). Content-based, not SHA/fast-forward-only: a merge commit that pulls the default branch down into staging with no staging-unique non-merge commit is caught too, since `new_commits` excludes merge commits and anything already reachable from `default_branch_tip`.
    - **no version tag on the repo yet** — `list_tags` empty (or no tag parses as semver) → the next version is `v0.1.0` **directly** (not bumped further from a synthetic `v0.0.0`) — the repo's first assigned version. Staging carries it as `v0.1.0-rc`; a default-branch push with no staging candidate behind it cuts it as a hotfix, `v0.1.0` full.
    - **`BranchRole.STAGING`** — when a version tag exists, the bump basis is the semver-max over BOTH full and `-rc` tags (`list_tags` filtered to version tags, ordered semver-aware, `v1.10.0 > v1.9.0`); bump the configured `version_increment` component off that max, append `-rc`. Successive staging pushes advance every time (`v1.2.1-rc`, then `v1.2.2-rc`) — no `-rc.N` counter, no re-tagging the same candidate.
    - **`BranchRole.RELEASE`** — two cases, both full releases (`prerelease=False`):
      - **promotion** — the highest `-rc` tag base reachable from `after` (`is_ancestor(bare, <that -rc tag's commit>, after)`, enumerated via `list_tags` filtered to `-rc` tags) that is greater than the last full release tag → adopt that candidate's base version, drop `-rc`, no further bump.
      - **hotfix** — no such reachable `-rc` candidate, and a version tag exists → bump `version_increment` off the last full release tag.
    - **`BranchRole.DEV`** — `Versioner.next` is never called (9.1/11.3 gate on `RELEASE`/`STAGING` only); out of scope for this task.

## Files & types

- edit `src/core/config.py` (`version_increment: Literal["major","minor","patch"]`)
- edit `src/commits/collector.py` (`GitCommitCollector.list_tags`, `GitCommitCollector.is_ancestor`, `GitCommitCollector.new_commits`)
- new `src/versioning/__init__.py`, `src/versioning/versioner.py` (`Version`, `Versioner`)

## Guards

- Reads the mirror (`RepoMirror.object_store_path`, tags, history) — reproducible, no network; constructed via constructor DI, never builds a concrete `RepoMirror`/`GitCommitCollector` itself.
- Branch role compared in **one place** — consumes `BranchRole`/`role_for_branch` (9.1); `Versioner` never re-derives it from a raw branch string.
- **Version derivation assumes preserved, append-only history on `staging` and the default branch** (no squash/rebase/amend/force-push; merges are real merges or fast-forwards — `docs/behavior/delivery.md#versioning`). Promotion detection via `-rc`-tag reachability (`is_ancestor`) is sound precisely because of this precondition — a rewritten history is unsupported and out of scope.
- Back-merge → `None`, never a spurious `-rc`, via the **content-based** `new_commits` primitive — NOT a SHA/fast-forward-only ancestor check, so a merge-commit back-merge (default merged into staging via a merge commit, no staging-unique work) is caught too, not only a fast-forward one.
- **Back-merge detection is a silent-failure surface** — a wrong check silently manufactures a spurious `-rc` or skips a real release. Mandatory red tests over a fixture mirror: (1) a fast-forward back-merge (`before..after` ⊆ default) → `None`; (2) the **hotfix round-trip** — a hotfix commit lands on the default branch and is released (a full-release tag, e.g. `v1.2.1`, points at it), then that hotfix is back-merged into `staging` via a **merge commit** with no staging-unique non-merge work → the staging push's `new_commits(bare, before, after, default_branch_tip)` is empty (the hotfix commit is already reachable from the default branch, filtered by `--not <default>`, and the merge commit itself is excluded by `--no-merges`) → `None`; (3) genuinely new non-merge commits on staging → a version. Pin the check specifically (via `new_commits`), not only input/output pairs.
- **Tag selection is semver-aware** — `v1.10.0 > v1.9.0`, never lexicographic; non-version tags ignored — the SAME parsing/ordering `SinceDeployWindow` (11.2.1) uses, both consuming `GitCommitCollector.list_tags` so the two never disagree.
- No tag on the repo → base `v0.1.0` (never a crash on an empty `list_tags`).
- Staging always bumps (never idempotently repeats a prior `-rc`) — the bump basis is the semver-max over full + `-rc` tags, per push.
- A default-branch push is a promotion (adopt the reachable candidate's base, no bump) or a hotfix (bump off the last full release) — never a third path.
- Increment component from `Settings` (validated `Literal`), not hardcoded.
- `Version` has exactly one render path (`__str__`); no second formatting call site.

## Verification

- No tags on the repo → first staging push → `v0.1.0-rc` (the repo's first version, not bumped further); a default-branch push with no staging candidate behind it → `v0.1.0` (hotfix).
- Two successive staging pushes with no intervening release → `v1.2.1-rc`, then `v1.2.2-rc` (each advances).
- A default-branch push whose work already rode a reachable `-rc` candidate → that candidate's base, `-rc` dropped, no further bump (promotion).
- A default-branch push with no staging candidate behind it → bump off the last full release (hotfix).
- A back-merge from the default branch into staging → `None` (no version), whether fast-forward or via a merge commit, via `new_commits`.
- With tags `v1.9.0`, `v1.10.0` present, the base is `v1.10.0` (semver-aware, not lexicographic).
