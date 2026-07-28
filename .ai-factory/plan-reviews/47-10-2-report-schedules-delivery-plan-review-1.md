## Code Review Summary

**Artifact:** Plan `47-10-2-report-schedules-delivery.md` (task 10.2 — Report schedules + delivery)
**Files Reviewed:** plan + spec `18-weekly-schedule-delivery.md` + targeted code (`report.py`, `collector.py`, `mirror.py`, `sync.py`, `served_repos.py`, `routing/*`, `delivery/*`, `sections/*`, `scripts/backfill.py`, `scripts/eval.py`, `main.py`, `config.py`)
**Risk Level:** 🔴 High — one confirmed runtime crash on a realistic first-report scenario.

### Context Gates
- **Roadmap** — OK. Plan `# Plan: 10.2 — Report schedules + delivery` matches `.ai-factory/ROADMAP.md:101`; the plan's guards (iterate `served_repos` not mirror-root; ensure-before-build; `None`→nothing; never read `branch_role`; idempotent) all trace to the contract line and spec `.ai-factory/specs/18-weekly-schedule-delivery.md`. WARN: none.
- **Architecture** — OK. New `scripts/report.py` is a composition root (concretes wired only there, mirroring `backfill.py`/`eval.py`); features receive abstractions via constructors; `resolve_canonical_ref` lands in infra (`src/github/mirror.py`). No boundary/dependency violation.
- **Rules** — `.ai-factory/RULES.md` is intentionally empty (no counter-defaults). No skill-context file present. No violations.

### Critical Issues

**1. The `EMPTY_TREE_SHA` fallback for `before` crashes `PerBranchSection` — a young/newly-served repo's first report throws.** (Task 4)

Task 4 falls back to `EMPTY_TREE_SHA` for `before` "when a repo whose whole history is younger than `delta`", and the plan asserts every section then resolves cleanly (summary→`None`, or the commits since cutoff). That holds for `SummarySection` and `RemainingSection`, but **not** for `PerBranchSection`, which is in the `daily` schedule (`[summary, per_branch, remaining]`).

`Report.build` renders every section with the same `(before, after)`. `PerBranchSection.render` (`src/changelog/sections/per_branch.py:41`) calls `GitCommitCollector.active_branches(bare, before, after)`, whose first line (`src/commits/collector.py:148`) is:

```python
before_time = self.commit_timestamp(repo_path, before).isoformat()
```

`commit_timestamp` (`collector.py:196`) runs `git show -s --format=%cI <ref>` with `check=True` and unconditionally does `datetime.fromisoformat(result.stdout.strip())`. On the empty-tree SHA git exits 0 but prints `tree 4b825dc6…` (a tree object has no commit date), so the parse raises:

```
ValueError: Invalid isoformat string: 'tree 4b825dc642cb6eb9a060e54bf8d69288fbee4904'
```

(Both facts verified against real git + CPython on this machine.) `report.build` propagates the exception; the per-served-repo loop in Task 5 has no guard, so the schedule run aborts.

Failure scenario — concrete and likely on day one: a repo first served today with commits only from this week runs under the `weekly` (7-day) window. `now - delta` is 7 days ago; no canonical commit is at-or-before that, so `before = commit_at_or_before(...) = None → EMPTY_TREE_SHA`. `after` = the current tip (a real SHA). `PerBranchSection` → `active_branches(bare, EMPTY_TREE_SHA, tip)` → `commit_timestamp(EMPTY_TREE_SHA)` → `ValueError`. The same fires under `daily` (1-day) for any repo whose first canonical commit is within the last day. This is precisely the "active window / whole history younger than delta" branch the plan intends to support, so the bug sits on the intended happy path, not an exotic edge.

This must be resolved before implementation. Options (pick one and pin it in the plan):
- Special-case `before == EMPTY_TREE_SHA` inside `active_branches`/`commit_timestamp` (treat the empty-tree boundary as "beginning of time" → `before_time` = a far-past date or unbounded `--until`), **or**
- Guard `PerBranchSection` (and any section deriving a time window from `before`) against the empty-tree `before`, **or**
- Have `TimeWindow.resolve` avoid handing `EMPTY_TREE_SHA` to sections that read `before`'s timestamp (e.g. anchor `before` on the repo's oldest reachable commit instead of the empty tree for the all-young case).

Whichever is chosen, Task 7 must add a `TimeWindow.resolve` → `Report.build` (with `per_branch`) test over a temp repo whose entire history is younger than `delta`, asserting a report is produced (or `None`) **without raising** — the current Task 7 wording tests `TimeWindow.resolve`'s return value in isolation and would miss this section-interaction crash.

### Issues (non-blocking but should be addressed)

**2. "One home per fact" is only partially applied — two canonical-ref copies remain.** (Task 3)

Task 3 extracts `resolve_canonical_ref` and migrates only `KnowledgeSync._canonical_ref`. Two byte-identical copies of the same policy survive:
- `CoordinationSeeder._canonical_ref` — `src/graph/coordination.py:37`
- `EpisodicBackfill._canonical_ref` — `src/episodic/backfill.py:62`

The task's own DEVIATION cites "One home per fact" as justification, yet after it the policy still has three homes. Either migrate all three delegators to `resolve_canonical_ref` (small, mechanical, and their existing tests pin the behavior), or state explicitly in Task 3 that these two are consciously left for a later sweep. As written the stated rationale and the delivered result disagree.

**3. No per-repo error isolation in the entrypoint loop.** (Task 5)

The per-served-repo loop (`ensure → resolve-plan → build → deliver`) has no `try/except` per iteration. Any single repo raising — the crash in Issue 1, a `mirror.ensure` network/auth failure, a `LookupError` from `clone_source` on a missing `GITHUB_ORG_LOGINS` entry, or an LLM timeout inside `build` — aborts the whole schedule run, so every later served repo silently gets no report that cadence. Fail-loud is defensible, but with a realistic crash trigger (Issue 1) present it means one young repo blocks all others. Decide explicitly: either wrap each repo in `try/except` with a logged per-repo failure and continue, or document in Task 5 that a single-repo failure intentionally aborts the run. The spec's "idempotent re-run" guard argues for continue-and-log so a transient failure on one repo doesn't starve the rest.

### Positive Notes
- Deviations are correctly identified and grounded: `TimeWindow.resolve`'s `NotImplementedError`, `ServedRepoStore`'s missing read API, the absent "newest commit at-or-before" primitive, and the canonical-ref extraction are all real and accurately described against the code.
- Task 2's `commit_at_or_before` reuses the exact `_rev_list(-1, --until=…)` idiom already proven in `active_branches` (`collector.py:160`) — consistent, no-raise, read-only.
- Backward-compat is handled with care: `compare=False` fields on `TimeWindow` and keyword-only `None`-default params on `report_for_schedule` keep `tests/changelog/test_schedule.py:39`/`:37` green (verified — equality is by `delta` alone, and the 2-arg call still constructs).
- Task 5's schema-execution list (`ingestion` + `knowledge` + `episodic` + `graph`) correctly matches `main.py:41-44`; the `ingestion/schema.sql` inclusion is what makes `served.all()` work on a fresh DB.
- The `served_repos` iteration read path (`SELECT org_id, repo … ORDER BY org_id, repo`, tuples with row-sourced `org_id`) satisfies the spec's authoritative-set + no-guessed-org_id guards.
- The delivery-plan handling (canonical ref passed only to avoid a fake branch; consuming only `telegram_channel`/`language`) matches the spec guard and the actual `DeliveryPlanResolver`/`DeliveryService`/`DeliveryPlan` shapes.

## Deferred observations
- Affects: repo tooling (`deploy/` does not yet exist) — Task 6 creates `deploy/report-crons.crontab` in a directory that is not present in the repo today; the file write will create it. No action needed, noted only so the implementer isn't surprised by a missing parent dir. Also minor: Task 6 should add `report-daily`/`report-weekly` to the `Makefile` `.PHONY` line (`Makefile:4`) alongside the new targets — an implementation nicety, not a plan gap.
