# Code review: 10.1.2 — Report sections (summary, per-branch, remaining)

Scope: `git diff HEAD` — three new `ReportSection` impls (`SummarySection`,
`PerBranchSection`, `RemainingSection`), the `open_tasks` parser +
`RemainingPromptBuilder`, `GitCommitCollector.active_branches`, a
`default_section_registry` wiring helper, and their tests.

## Verification performed

- `uv run pytest` — **138 passed** (21 in `tests/changelog/`, no regressions
  from the `collector.py` change).
- Exercised `GitCommitCollector.active_branches` against a purpose-built real
  git repo (branches at controlled commit dates) — the git plumbing that the
  section unit tests mock away. Confirmed: newest in-window SHA selected as
  `branch_after`; `branch_before` resolved as the tip at/before the lower
  boundary; branches with no in-window commit are omitted; `--since/--until`
  boundaries are inclusive (matching the plan's DEVIATION note).
- Confirmed the two-dot ranges the sections feed `resolver.resolve`
  (`branch_before..branch_after`, `before..after`) are exclusive of the lower
  bound, so `SummarySection` and each `PerBranchSection` sub-part cover the
  same `(before, after]` semantics with no lower-bound double-count.
- Confirmed `dataclasses.replace(change, repo=repo)` works on the
  `frozen=True, slots=True` `LinkedChange` and that `Reasoner.narrate` reads
  only `change.repo` (for retrieval scoping) and `change.commits.commits` (for
  the query/prompt) — the inner `CommitContext.repo` still holding the bare
  path is never read, so leaving it unrebound is harmless.

The implementation faithfully realizes the plan and the spec; the empty-window
short-circuit, the repo-KEY rebind, the exact `[ ]`-only parse, and the
no-LLM-call short-circuits are all correct and well-tested. Findings below are
low-severity design/robustness observations, not blocking defects.

## Findings

### 1. (Low) Overlapping/alias branches produce duplicate per-branch narrations and duplicate LLM calls

`src/changelog/sections/per_branch.py:42-52` narrates **every** branch
`active_branches` returns, keyed only by branch name. On a bare
`git clone --mirror`, `refs/heads/*` holds every remote branch, and two
branches can share the same in-window range:

- **Failure scenario:** a `staging`/`release` (or `master`) branch pointing at
  the same tip as `main`. Both resolve to the identical `branch_before..branch_after`
  range → `resolver.resolve` returns identical `LinkedChange`s → `narrate` is
  called twice and the report contains two byte-identical sub-parts under
  different headers. A freshly-merged-but-undeleted feature branch produces a
  near-duplicate sub-part whose commits are already inside `main`'s sub-part.
  Verified live: a branch created at `main`'s tip is enumerated alongside
  `main` with the same `(branch_before, branch_after)` pair.

Impact: redundant report prose plus wasted LLM cost/latency (one `generate`
per duplicate). This is arguably within the spec's "branches with commits in
the range" wording, so it may be intended — but if not, dedup by resolved
range (or by `branch_after` SHA) before narrating, and/or skip the canonical
branch here since `SummarySection` already covers it holistically. Flagging for
an explicit decision rather than silent acceptance.

### 2. (Low / deferred to 10.2) `active_branches` is not no-raise when `before`/`after` is not a commit object

`src/commits/collector.py:148-149` calls `commit_timestamp(...)`, which runs
with `check=True` and then `datetime.fromisoformat(...)`. If a future
`TimeWindow` (10.2) resolves a young repo's lower bound to `EMPTY_TREE_SHA`
(the value this very method uses as a `branch_before` fallback) or to any
non-commit ref, `commit_timestamp` raises `CalledProcessError`/`ValueError`,
which propagates up through `PerBranchSection.render` and aborts the whole
`Report.build`. The method's docstring scopes its no-raise guarantee to
`for-each-ref`/`rev-list` and states `before`/`after` are "assumed-valid
refs", so this is documented, not a current bug (`TimeWindow` is unbuilt and
no caller passes empty-tree today). Heads-up for 10.2: ensure `TimeWindow`
never hands a non-commit `before` to the sections, or make the window-boundary
lookup tolerate repo-start.

## Notes (non-issues, verified OK)

- `open_tasks` regex `^\s*[-*]\s*\[\s\]` is correctly distinct from
  `linked_change._DONE_LINE_RE` (`[xX]`); the two never overlap. A degenerate
  `- [ ]` with no trailing text would yield an empty-string task (kept in the
  list), but real roadmap lines always carry text — not worth guarding.
- `%cI` (committer date) matches git's `--since/--until` filtering basis
  (also committer date) — no author-vs-committer-date mismatch.
- `org_id` is unused in all three sections; correct — the ABC mandates the
  parameter and `mirror.ensure` is the caller's precondition.
- `default_section_registry` pins the `summary`/`per_branch`/`remaining` keys
  in one home; no import cycle (`sections/__init__.py` imports submodules;
  submodules import `changelog.section`, not the package).
- `narrate_report` genuinely does not exist in `reasoner.py`; the spec's
  "retire" is a no-op, correctly handled as a DEVIATION with no edit.
