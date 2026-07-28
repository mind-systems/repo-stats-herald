# Code Review: 11.1 — Versioning + back-merge skip

**Plan:** `.ai-factory/plans/49-11-1-versioning-back-merge-skip.md`
**Spec:** `.ai-factory/specs/19-versioning.md` → `docs/behavior/delivery.md#versioning`
**Scope reviewed:** `src/core/config.py`, `src/commits/collector.py`, `src/versioning/__init__.py`, `src/versioning/versioner.py`, `tests/commits/test_collector.py`, `tests/versioning/test_versioner.py`

## Verdict

The change is correct against the spec and its verification list. Full suite green (171 passed), including the mandated back-merge red cases at both the `new_commits` primitive and `Versioner.next` levels. No correctness, security, or runtime-breakage defect found. One low-severity, non-blocking defensive-consistency note below.

## What was verified

- **`Settings.version_increment`** — `Literal["major","minor","patch"] = "patch"`, `Literal` added to the `typing` import. An invalid value is a pydantic startup error (no silent no-op), as required. Read-once/inject discipline preserved (nothing reads it inside a feature).
- **Collector primitives** follow the class idiom (`-C <repo>`, `check=False` no-raise, `splitlines()`-and-drop-blank):
  - `list_tags` is parse-agnostic — returns `nightly`/`build-42` verbatim; filtering is the caller's `Version.parse` job (confirmed by `test_list_tags_returns_all_tag_names_parse_agnostic`). Reusable by `SinceDeployWindow` (11.2.1).
  - `is_ancestor` returns `returncode == 0`; unknown ref → `False`, never raises (confirmed).
  - `new_commits` — `rev-list <before>..<after> --no-merges --not <exclude_ref>`. The `--not` is functionally in effect despite the intervening `--end-of-options` (proven by `test_new_commits_empty_for_merge_commit_back_merge`, which only reads empty if main's commits are excluded). A merge-commit back-merge and a fast-forward back-merge both yield `()`; genuinely new staging work yields the introduced SHA.
- **`Version`** — single render path via `__str__` (`v1.2.0` / `v1.2.0-rc`, no `-rc.N`); regex `^v?(\d+)\.(\d+)\.(\d+)(-rc)?$` rejects non-version and malformed tags. Ordering is semver-aware via `total_ordering` + a `(major, minor, patch, prerelease-rank)` sort key — `v1.10.0 > v1.9.0` and a full release ranks above its own `-rc`. `bump` produces a full version and raises on an unknown component. `base`/`as_rc` compose without re-formatting.
- **`Versioner.next`** — takes `BranchRole` as given (never re-derives from a branch string); reads only the bare store via `object_store_path`. Staging: back-merge guard first (`new_commits` empty → `None`), else `v0.1.0-rc` when no version tag, else bump the semver-max (over full+rc) and append `-rc`. Release: promotion adopts the highest reachable `-rc` whose base exceeds the last full release; else hotfix bumps the last full release; else `v0.1.0`. The `base > last_full` filter correctly prevents re-promoting an already-released candidate. Every spec verification bullet has a matching passing test.

## Findings

### 1. `new_commits` leaves the `<before>..<after>` range unprotected by `--end-of-options` (Low, non-blocking)

`src/commits/collector.py:233-244` places `f"{before}..{after}"` *before* the `--end-of-options` marker, which sits only ahead of `exclude_ref`. Every other method on this class (`first_parent_steps`, `changed_paths`, `read_blob`, `_rev_list`) deliberately puts `--end-of-options` ahead of the caller-supplied refs so a ref beginning with `-` can never be read as an option. Here the range token is the one caller-supplied argument left outside that guard.

This is not a current-behavior bug: `before`/`after` are commit SHAs resolved upstream by the webhook receiver, never dash-prefixed or attacker-arbitrary, and the suite passes. It is a defense-in-depth/consistency gap only — worth aligning with the class idiom by moving `--end-of-options` to precede the range (git accepts `A..B` after `--end-of-options`). Flagging, not blocking.

## Notes (not defects)

- `Versioner.next` returns `None` implicitly for `BranchRole.DEV`. This matches the spec (DEV is never called; callers gate on RELEASE/STAGING) and the `Version | None` return type, so it is intentional, not a missing branch.
- The "only `-rc` tags exist, none reachable, no full release" release case returning `v0.1.0` is a documented, intentional unification in the plan (Task 4), consistent with the no-tag rule; the spec leaves it implicit. Acceptable.
- No composition-root wiring of `Versioner` is present, correctly deferred to 11.3 per the plan scope.
