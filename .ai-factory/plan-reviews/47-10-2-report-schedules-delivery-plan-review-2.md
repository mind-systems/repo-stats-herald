## Code Review Summary

**Artifact:** Plan `47-10-2-report-schedules-delivery.md` (task 10.2 — Report schedules + delivery), round 2
**Files Reviewed:** plan + spec `18-weekly-schedule-delivery.md` + round-1 review + targeted code (`changelog/report.py`, `commits/collector.py`, `github/mirror.py`, `ingestion/served_repos.py`, `core/config.py`, `changelog/sections/*`, `routing/resolver.py` + `models.py`, `delivery/service.py` + `telegram.py`, `knowledge/sync.py`, `graph/coordination.py`, `episodic/backfill.py`, `scripts/backfill.py` + `eval.py`, `main.py`, `tests/changelog/test_schedule.py`)
**Risk Level:** 🟡 Medium — round-1's three findings are all resolved; one new correctness gap on the empty-repo path the plan itself constructs.

### Context Gates
- **Roadmap** — OK. `# Plan: 10.2 — Report schedules + delivery` matches `.ai-factory/ROADMAP.md:101`; the plan's guards (iterate `served_repos` not mirror-root; ensure-before-build; `None`→nothing; consume only `telegram_channel`/`language`, never `branch_role`; idempotent) all trace to the contract line and spec `.ai-factory/specs/18-weekly-schedule-delivery.md`. WARN: none.
- **Architecture** — OK. `scripts/report.py` is a composition root (concretes wired only there, mirroring `backfill.py`/`eval.py`); features receive abstractions via constructors; `resolve_canonical_ref` lands in infra (`src/github/mirror.py`, co-located with `RepoMirror.default_branch`). No boundary/dependency violation.
- **Rules** — `.ai-factory/RULES.md` is intentionally empty (its own note says so). No skill-context file at `.ai-factory/skill-context/aif-review/SKILL.md`. No violations.

### Round-1 findings — all resolved
- **Issue 1 (EMPTY_TREE crash in `PerBranchSection`)** → Task 2 now makes `active_branches` empty-tree-safe for `before == EMPTY_TREE_SHA` (skip `commit_timestamp`, `before_time = None`, drop `--since`, `branch_before = EMPTY_TREE_SHA`), and Task 7 adds the required section-interaction crash-guard test. Verified against `collector.py:148` and `per_branch.py:41`. **See the new finding below — the sibling `after == EMPTY_TREE_SHA` path is still unguarded.**
- **Issue 2 (partial "one home per fact")** → Task 3 now migrates **all three** copies (`sync.py:35`, `coordination.py:37`, `backfill.py:62`) onto `resolve_canonical_ref`; all three verified byte-identical to the extracted policy.
- **Issue 3 (no per-repo error isolation)** → Task 5 now wraps each served repo's `ensure → resolve-plan → build → deliver` in `try/except Exception` with logged failure + `continue` + run-level summary.
- **Deferred (Makefile `.PHONY`, missing `deploy/`)** → Task 6 now adds `report-daily`/`report-weekly` to `.PHONY` (confirmed `Makefile:4` = `.PHONY: install run tunnel dev eval test`) and notes `deploy/` is created by the write (confirmed absent today).

### Critical Issues

**1. The empty-repo fallback `(EMPTY_TREE_SHA, EMPTY_TREE_SHA)` still crashes `PerBranchSection` — Task 2's fix guards `before` but not `after`.** (Tasks 2 & 4)

Task 4 says: *"If `after` is `None` (empty repo — no commits at all), return `(EMPTY_TREE_SHA, EMPTY_TREE_SHA)` so every section sees an empty range → `Report.build` → `None`."* That claim does not hold for `PerBranchSection`, which is in the `daily` schedule.

`Report.build` (`report.py:53-64`) renders **every** section with the same `(before, after)` — there is no short-circuit. With `(EMPTY_TREE_SHA, EMPTY_TREE_SHA)`, `PerBranchSection.render` (`per_branch.py:41`) calls `active_branches(bare, EMPTY_TREE_SHA, EMPTY_TREE_SHA)`, whose first two lines (`collector.py:148-149`) are:

```python
before_time = self.commit_timestamp(repo_path, before).isoformat()
after_time  = self.commit_timestamp(repo_path, after).isoformat()   # after == EMPTY_TREE_SHA
```

Task 2 special-cases only `before == EMPTY_TREE_SHA`. Line 149's `commit_timestamp(after)` on the empty-tree SHA runs `git show -s --format=%cI 4b825dc6…`, which prints `tree 4b825dc6…` (a tree has no commit date), so `datetime.fromisoformat` raises `ValueError` — the exact failure mode round-1 documented, now on the `after` side. This runs before the branch loop, so an empty repo with no branches still hits it.

Failure scenario: a served repo with zero commits (a freshly created GitHub repo added to the served set) under the `daily` schedule. `commit_at_or_before(ref, now)` → `None` → `after = EMPTY_TREE_SHA`; `before = EMPTY_TREE_SHA`. `SummarySection`/`RemainingSection` correctly yield `None` (git special-cases `EMPTY_TREE..EMPTY_TREE` / reads a blob at `after` that isn't there), but `PerBranchSection` raises. Task 5's per-repo `try/except` catches it, so the run does **not** abort — but the plan's stated behavior ("every section → `None`") is wrong: the repo is logged as **failed** (not skipped-empty) on **every cadence**, producing a recurring exception line for each empty served repo.

Fix — pick one and pin it in the plan:
- Extend Task 2 so `active_branches` is empty-tree-safe for `after == EMPTY_TREE_SHA` too (the natural form: when `after == EMPTY_TREE_SHA` the window is empty → return `[]` immediately; more generally, treat either boundary being the empty tree without calling `commit_timestamp` on it), **or**
- Have Task 4 return a range that keeps `after` a real SHA for the empty-repo case (there is none — so this collapses to the collector fix), **or**
- Guard `PerBranchSection` against an empty-tree `after`.

Whichever is chosen, Task 7 should add the empty-repo case (`after == EMPTY_TREE_SHA`) to the section-interaction test — its current wording covers only the *young-repo* case (`before == EMPTY_TREE_SHA`, real `after`) and would miss this.

### Positive Notes
- Signatures verified end-to-end: `default_section_registry(mirror, resolver, reasoner, collector, source_strategy, llm, remaining_prompt)` (`sections/__init__.py:14`), `DeliveryPlanResolver.resolve(org_id, repo, branch)` (`routing/resolver.py:20`), `DeliveryService.deliver(plan, note)` (`delivery/service.py:18`), `TelegramClient(token)` (`delivery/telegram.py:7`), `Report.build(repo, org_id, lang="ru")` (`report.py:53`), `RepoMirror.ensure(repo, org_id)`/`sweep_worktrees()`/`object_store_path` — all match the plan's call sites.
- `DeliveryPlan` (`routing/models.py:11`) confirms `telegram_channel`/`language` are the only fields the report path needs; `branch_role`/`is_release`/`is_prerelease` are present but the plan correctly forbids reading them (spec guard).
- Backward-compat is sound: `compare=False`, `default=None` fields on `TimeWindow` keep `TimeWindow(timedelta(days=1))` constructible and delta-only equality intact (`test_schedule.py:39`), and keyword-only `None`-default params on `report_for_schedule` keep the 2-arg call green (`test_schedule.py:37`). Field ordering is valid (non-default `delta` first).
- Task 5's schema list (`ingestion` + `knowledge` + `episodic` + `graph`) matches `main.py:41-44` exactly, which is what makes `served.all()` and the reasoner path self-sufficient on a fresh DB.
- `commit_at_or_before` reuses the proven `_rev_list(-1, --until=…, --end-of-options, ref)` idiom (`collector.py:160,185`) — consistent, read-only, `check=False`.
- `ServedRepoStore.all()` (`SELECT org_id, repo … ORDER BY org_id, repo`, row-sourced `org_id`) satisfies the authoritative-set + no-guessed-org_id guards; `served_repos.py` today exposes only `add`/`remove`, confirming the read-path DEVIATION is real.
- The quiet-window path is correct: canonical tip older than `now - delta` gives `before == after == tip`, so `EMPTY_TREE`-free `commit_timestamp(tip)` calls succeed and every section returns `None` → `build` → `None`. The crash is confined to the empty-repo (`after == EMPTY_TREE`) case above.

## Deferred observations
- Affects: task 10.3 (report localization) — Task 5 hard-codes delivery to `plan.language` (default `"ru"`) and the plan notes 10.3 later threads non-RU via the localizer. No action here; the single-language build is the correct 10.2 scope, and 10.3 owns the multi-language extension. Noted only so the RU-only delivery isn't mistaken for an omission. [dismissed]
