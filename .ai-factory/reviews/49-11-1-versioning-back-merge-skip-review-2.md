# Code Review (Re-review): 11.1 — Versioning + back-merge skip

**Plan:** `.ai-factory/plans/49-11-1-versioning-back-merge-skip.md`
**Spec:** `.ai-factory/specs/19-versioning.md` → `docs/behavior/delivery.md#versioning`
**Prior review:** `.ai-factory/reviews/49-11-1-versioning-back-merge-skip-review-1.md`
**Scope reviewed:** `src/core/config.py`, `src/commits/collector.py`, `src/versioning/__init__.py`, `src/versioning/versioner.py`, `tests/commits/test_collector.py`, `tests/versioning/test_versioner.py`

## Verdict

The single prior finding is **Fixed**. Full suite green (171 passed), including the mandated back-merge red cases. No new correctness, security, or runtime-breakage defect found.

## Per-finding verdicts

### Finding 1 — `new_commits` left the `<before>..<after>` range unprotected by `--end-of-options` — **Fixed**

The exclusion was rewritten from the `--not <exclude_ref>` flag to a literal `^exclude_ref` revision arg, letting `--end-of-options` precede **both** caller-supplied refs. Current content, `src/commits/collector.py:241-255`:

```python
        result = subprocess.run(
            [
                self._git_bin,
                "-C",
                repo_path,
                "rev-list",
                "--no-merges",
                "--end-of-options",
                f"{before}..{after}",
                f"^{exclude_ref}",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
```

Both `f"{before}..{after}"` and `f"^{exclude_ref}"` now sit after `--end-of-options`, so no caller-supplied ref can be misread as an option — matching the defensive idiom used by `changed_paths`/`read_blob`/`_rev_list`. The docstring (`collector.py:234-239`) documents why `^ref` is used instead of a trailing `--not` (a `--not` after `--end-of-options` would itself error). The semantics are identical: `rev-list --no-merges A..B ^exclude_ref` = non-merge commits reachable from `after`, excluding `before`'s and `exclude_ref`'s history.

**Evidence it still works:** `test_new_commits_empty_for_merge_commit_back_merge` (which reads empty only if `^main` actually excludes main's hotfix commit) and `test_merge_commit_back_merge_round_trip_of_a_released_hotfix_returns_none` both pass, plus the fast-forward and staging-unique-work cases. 20/20 targeted, 171/171 full suite.

## New-issue scan

- **Refactor blast radius** — the fix is confined to `new_commits`; `versioner.py` and `config.py` are byte-for-byte unchanged from the prior (already-accepted) pass. No other call site touches `new_commits`.
- **`^exclude_ref` on a missing ref** — a non-existent `exclude_ref` makes git exit non-zero → `()` via the no-raise fallback, same as the previous `--not` form. In the staging path `exclude_ref` is `mirror.default_branch(repo)`, which always resolves, so this is not reachable in practice.
- **Argument order** — `--no-merges` (an option) correctly precedes `--end-of-options`; the two revision args follow it. Correct.
- Re-confirmed from the prior pass and unchanged: `Version` single render path and semver-aware ordering, the `base > last_full` promotion filter preventing re-promotion, the `v0.1.0` first-version fallback, `BranchRole.DEV` intentionally falling through to `None`, and the read-only bare-store access. No composition-root wiring (correctly deferred to 11.3).

REVIEW_PASS
