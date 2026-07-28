# Code Review: 11.2.1 — SinceDeployWindow (red tests)

**Plan:** `.ai-factory/plans/50-11-2-1-sincedeploywindow-red-tests.md`
**Governing spec:** `.ai-factory/specs/51-since-deploy-window.md`

## Scope

The change is purely additive — three new files, no existing source touched:

- `src/changelog/windows/__init__.py` (empty package marker)
- `src/changelog/windows/since_deploy.py` (`SinceDeployWindow`)
- `tests/changelog/test_since_deploy_window.py` (guard tests)

(The remaining staged files are planning artifacts: the plan, its JSON, and two plan-reviews.)

## Verification

- Ran `uv run pytest tests/changelog/test_since_deploy_window.py -q` — **9 passed**.
- Read all three new files in full and cross-checked every API against ground truth:
  `ReportWindow.resolve` contract (`src/changelog/report.py:12-24`), `GitCommitCollector.list_tags`
  and `EMPTY_TREE_SHA` (`src/commits/collector.py:196-209, 23`), `Version.parse` / `@total_ordering`
  with full-ranks-above-own-`-rc` (`src/versioning/versioner.py:12-56`), and `BranchRole`
  members (`src/routing/models.py:5-8`).

## Correctness assessment

- **STAGING selection is correct.** `max` over *all* parsed pairs yields the full `v1.2.0`
  when both `v1.2.0-rc` and `v1.2.0` exist (full `_sort_key` `(1,2,0,1)` > rc `(1,2,0,0)`),
  and yields a later `v1.3.0-rc` once its base outranks — algebraically identical to
  `max(last full, last rc)`, exactly as the spec requires. No `-rc` special-casing, as
  mandated. Confirmed by the two staging tests.
- **RELEASE selection is correct.** Filtering to `not version.prerelease` before `max`
  picks the last full release and ignores a higher `-rc`, verified by
  `test_release_ignores_a_higher_rc_while_staging_picks_it`.
- **Semver, not lexicographic** — `v1.10.0 > v1.9.0` via `Version` ordering, verified.
- **Non-version tags ignored** — `Version.parse` returns `None` for `nightly`/`build-42`,
  filtered out in the comprehension; verified.
- **No-tag → root** — empty `candidates` yields `before = EMPTY_TREE_SHA` for both
  environments; verified.
- **Shared-primitive reuse** — tags read only via the injected `collector.list_tags(bare)`;
  the `StubCollector` spy test pins the call and that the base comes from the returned
  tuple. No private `git tag` shelling.
- **`DEV`/`else` guard** — `resolve` raises `ValueError` before touching `candidates`,
  closing the plan-review finding-1 gap (no latent `NameError`); verified by
  `test_unsupported_environment_raises`.
- **Invariant preserved** — `resolve` never calls `mirror.ensure`; it only reads
  `mirror.object_store_path(repo)`. The class docstring states this, echoing `ReportWindow`.
- **`before` fidelity** — the original tag string (not a re-rendered `str(Version)`) is
  returned, preserving exact spelling as a valid git ref.
- **`after = "HEAD"`** — literal ref per spec. The plan already flagged, as a deferred
  observation for 11.2.2, that downstream consumers must treat `after` as a live ref
  against the ensured bare store rather than a pinned SHA; that is a consumer concern, not
  a defect here.

## Architecture / rules

`changelog` depends on the public value objects/classes of `versioning` (`Version`),
`routing` (`BranchRole`), `commits` (`GitCommitCollector`), and `github` (`RepoMirror`),
all injected through the constructor — consistent with the cross-feature rule in
`.ai-factory/ARCHITECTURE.md` and with `Versioner`'s own shape. No env reads, no concrete
wiring in the class. RULES.md is empty; nothing to violate.

## Findings

None. Implementation matches the plan and spec, tests are green, and every guard the spec
pins is covered.

REVIEW_PASS
