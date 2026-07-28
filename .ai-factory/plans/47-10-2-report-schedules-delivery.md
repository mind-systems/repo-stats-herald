# Plan: 10.2 — Report schedules + delivery

## Context
Add the composition-root entrypoint (`scripts/report.py --schedule <name>`) plus its two crons that build a named schedule's report for every served repo and deliver it to that org's Telegram channel — the leg that makes reports actually fire. Reaching the entrypoint forces two pieces the earlier tasks deferred to "the 10.2 entrypoint": `TimeWindow.resolve` (a real git range over the mirror) and a served-repo iteration read path.

## Settings
- Testing: minimal
- Logging: minimal
- Docs: no

## Ground-truth notes (read before implementing)

- Spec `.ai-factory/specs/18-weekly-schedule-delivery.md` lists only `scripts/report.py` under "Files & types", but the existing code forces four adjacent changes. Each is a deliberate DEVIATION grounded in the actual code, annotated below; they are conformance to ground truth, not scope creep:
  - `src/changelog/report.py` — `TimeWindow.resolve` **raises `NotImplementedError("TimeWindow.resolve (git range over the mirror) lands with the 10.2 entrypoint")`**. This task owns that implementation, and the spec body itself says "the window `resolve` ... read[s] an already-fetched bare store."
  - `src/ingestion/served_repos.py` — `ServedRepoStore` exposes only `add`/`remove`; the spec's "iterate `served_repos`" has no read API to call. A read method is required.
  - `GitCommitCollector` has no public "newest commit at-or-before a timestamp" primitive; `TimeWindow.resolve` needs one (the private `_rev_list(..., "--until=...")` already used by `active_branches` is the pattern). Separately, `active_branches` calls `commit_timestamp` on both `before` and `after`, either of which raises on `EMPTY_TREE_SHA` — `TimeWindow.resolve` legitimately produces `EMPTY_TREE_SHA` as `before` (young repo) and as both boundaries (empty repo), so the collector must be made empty-tree-safe on both sides (Task 2, fixes the review's critical crash).
  - The 3.6 canonical-ref policy is duplicated byte-for-byte across three private methods (`KnowledgeSync._canonical_ref`, `CoordinationSeeder._canonical_ref`, `EpisodicBackfill._canonical_ref`: `canonical_refs.get(repo)` else `mirror.default_branch(repo)`). Both `TimeWindow.resolve` and the delivery-plan step need it too; extract to one home and collapse all three onto it rather than adding a fourth copy ("the 3.6 policy value").
- Delivery consumes only `plan.telegram_channel` + `plan.language`. Neither depends on the branch (`telegram_channel = telegram_channels.get(org_id)`, `language = "ru"`), so the canonical ref passed to `DeliveryPlanResolver.resolve` only affects `branch_role`/`is_release`/`is_prerelease`, which the report path must never read (spec guard).
- Section wiring (already built): `default_section_registry(mirror, resolver, reasoner, collector, source_strategy, llm, remaining_prompt)` in `src/changelog/sections/__init__.py`; `report_for_schedule(schedule, registry)` and `schedule_by_name(schedules, name)` in `src/changelog/report.py`. Reference composition roots: `scripts/backfill.py`, `scripts/eval.py`.

## Tasks

### Phase 1: Supporting primitives

- [x] **Task 1: Served-repo iteration read path**
  Files: `src/ingestion/served_repos.py`
  Add `async def all(self) -> list[tuple[int, str]]` to `ServedRepoStore`: `SELECT org_id, repo FROM served_repos` (add an `ORDER BY org_id, repo` for stable, idempotent iteration), returning `(org_id, repo)` tuples. This is the authoritative served set the entrypoint iterates; `org_id` must come from the row, never guessed from a mirror directory name (spec guard).

- [x] **Task 2: Git primitives — commit-at-or-before + empty-tree-safe branch window**
  Files: `src/commits/collector.py`
  Two collector changes, both read-only and no-raise in the existing style:
  - Add `commit_at_or_before(self, repo_path: str, ref: str, when: datetime) -> str | None`: run `git -C <repo_path> rev-list -1 --until=<when.isoformat()> --end-of-options <ref>` (`check=False`), return the single SHA or `None` when the ref has no commit at or before `when`. Reuse `_rev_list` internally if convenient.
  - **Make `active_branches` empty-tree-safe on both boundaries** (fixes the review's critical crash on both the `before` and `after` sides). Its first two lines are `before_time = self.commit_timestamp(repo_path, before)` and `after_time = self.commit_timestamp(repo_path, after)`, each running `git show -s --format=%cI <ref>` — on `EMPTY_TREE_SHA` git prints `tree 4b825dc6…` (a tree has no commit date) and `datetime.fromisoformat` raises `ValueError`. `TimeWindow.resolve` (Task 4) legitimately hands `EMPTY_TREE_SHA` as `before` (young repo — whole in-window history younger than `delta`) and, for an empty repo with no commits at all, as **both** `before` and `after`; `PerBranchSection` is in the `daily`/`weekly` schedules, so this fires on a young or empty served repo's report. Fix, guarding each boundary before its `commit_timestamp` call:
    - `after == EMPTY_TREE_SHA` → the window ends before any commit exists, so no branch can be active: **return `[]` immediately** (before computing either timestamp). This covers the empty-repo `(EMPTY_TREE_SHA, EMPTY_TREE_SHA)` range.
    - `before == EMPTY_TREE_SHA` (with a real `after`) → treat as "beginning of time": skip `commit_timestamp(before)`, set `before_time = None`, omit the `--since=<before_time>` filter from the in-window `rev-list`, skip the `at_or_before` lookup, and set `branch_before = EMPTY_TREE_SHA` for every active branch.
    This matches the collector's already-documented empty-tree role ("nothing existed yet", `collector.py:22-24`) and keeps the log-range consumers (`LinkedChangeResolver` → `git log EMPTY_TREE..after`, which git special-cases) unchanged.

- [x] **Task 3: Extract the 3.6 canonical-ref policy to one home**
  Files: `src/github/mirror.py`, `src/knowledge/sync.py`, `src/graph/coordination.py`, `src/episodic/backfill.py`
  Add a module-level `resolve_canonical_ref(repo: str, canonical_refs: dict[str, str], mirror: RepoMirror) -> str` in `src/github/mirror.py` (co-located with `RepoMirror.default_branch`), implementing the current policy: return `canonical_refs.get(repo)` if set, else `mirror.default_branch(repo)`. Then migrate **all three** existing byte-identical copies of this policy to delegate to it (behavior identical — each class's existing tests pin it and must stay green):
  - `KnowledgeSync._canonical_ref` (`src/knowledge/sync.py:35`)
  - `CoordinationSeeder._canonical_ref` (`src/graph/coordination.py:37`)
  - `EpisodicBackfill._canonical_ref` (`src/episodic/backfill.py:62`)
  Each retains its thin `_canonical_ref(repo)` wrapper (calling `resolve_canonical_ref(repo, self._canonical_refs, self._mirror)`) so no call sites change. DEVIATION: these files are not in the spec's list; justified by "One home per fact" and the spec's phrase "the 3.6 policy value" (one shared policy, now consumed in a fourth place — the report entrypoint). Migrating all three closes the review's finding that the rationale and result would otherwise disagree.

### Phase 2: Time-window resolution

- [x] **Task 4: Implement `TimeWindow.resolve` (git range over the mirror)** (depends on Task 2, Task 3)
  Files: `src/changelog/report.py`
  Replace the `NotImplementedError` stub with a real resolution, and give `TimeWindow` the collaborators it needs while preserving its delta-only equality:
  - Fields: keep `delta` (the only compared field). Add `mirror: RepoMirror | None`, `collector: GitCommitCollector | None`, `canonical_refs: dict[str, str] | None`, each as `dataclasses.field(default=None, compare=False)` so `TimeWindow(timedelta(days=1))` still constructs and `==` still compares by `delta` alone (keeps `tests/changelog/test_schedule.py:39` green). Keep `frozen=True`.
  - `resolve(repo)`: require the injected deps (raise a clear `ValueError`/`RuntimeError` if any is `None` — an unwired window is a composition-root bug, not a silent empty range). Then:
    - `ref = resolve_canonical_ref(repo, self.canonical_refs, self.mirror)` (Task 3).
    - `bare = str(self.mirror.object_store_path(repo))` — the sections read this same bare store.
    - `now = datetime.now(timezone.utc)`; `after = self.collector.commit_at_or_before(bare, ref, now)` (the canonical-ref tip); `before = self.collector.commit_at_or_before(bare, ref, now - self.delta)`.
    - Fall back to `EMPTY_TREE_SHA` (import from `src.commits.collector`) when `before`/`after` is `None`. A `None` `before` (no canonical commit older than the cutoff — i.e. the repo's whole in-window history is younger than `delta`) is the normal first-report-of-a-young-repo case; Task 2's empty-tree-safe `active_branches` is what keeps `PerBranchSection` from crashing on this `before`. If `after` is `None` (empty repo — no commits at all), return `(EMPTY_TREE_SHA, EMPTY_TREE_SHA)`; Task 2's `after == EMPTY_TREE_SHA` guard is what lets `PerBranchSection` see this empty range as "no active branches" (`[]`) rather than crashing, so every section yields `None` → `Report.build` → `None` (the repo is logged skipped-empty, not failed).
    - Return `(before, after)`.
  - Behavior this produces (matches spec verification): a quiet window — canonical tip older than `now - delta` — yields `before == after` (empty `before..after`), so every section returns `None` and `Report.build` returns `None` → nothing delivered. An active window yields the commits since the cutoff; when the whole history is younger than `delta`, `before = EMPTY_TREE_SHA` and every section (summary, per-branch via Task 2's fix, remaining) renders over the full history without raising. Anchoring is on the repo's canonical ref (the same ref the delivery plan resolves through); document in the docstring that a report window is anchored on the canonical ref and is wall-clock-relative (`now`).
  - Extend `report_for_schedule(schedule, registry, *, mirror=None, collector=None, canonical_refs=None)`: build `TimeWindow(timedelta(days=schedule.window), mirror=mirror, collector=collector, canonical_refs=canonical_refs)`. New params are keyword-only with `None` defaults so the existing 2-arg call in `tests/changelog/test_schedule.py:37` stays green; the entrypoint passes the real deps.

### Phase 3: The entrypoint

- [x] **Task 5: `scripts/report.py` composition root** (depends on Task 1, Task 4)
  Files: `scripts/report.py`
  New `--schedule <name>` entrypoint. Argparse: one required `--schedule` argument. Assembly only (mirror `scripts/backfill.py` + `scripts/eval.py`):
  - `settings = get_settings()`; `pool = await create_pool(settings.postgres_dsn)`. Execute the schemas the pipeline reads so a fresh run is self-sufficient: `ingestion/schema.sql` (served_repos), `knowledge/schema.sql`, `episodic/schema.sql`, `graph/schema.sql` (same pattern as `main.py`/`backfill.py`).
  - Build concretes: `OllamaClient`, `OllamaEmbedder`, `PgVectorStore`, `PgEpisodicStore`, `PgProjectGraph`, `Reasoner(...)` (as `scripts/eval.py` wires it), `GitCommitCollector`, `AiFactorySourceStrategy`, `LinkedChangeResolver(collector, strategy)`, `RemainingPromptBuilder`, and the `RepoMirror` (`GitHubAppAuth` + `clone_source` closure, copied from `backfill.py`; call `mirror.sweep_worktrees()` once before any `ensure`).
  - `registry = default_section_registry(mirror, resolver, reasoner, collector, strategy, llm, remaining_prompt)`.
  - `schedule = schedule_by_name(settings.report_schedules, args.schedule)`; `report = report_for_schedule(schedule, registry, mirror=mirror, collector=collector, canonical_refs=settings.canonical_refs)` (raises on an unknown section key — the intended startup error).
  - `plan_resolver = DeliveryPlanResolver(settings)`; `delivery = DeliveryService(TelegramClient(settings.telegram_bot_token))`; `served = ServedRepoStore(pool)`.
  - Per served repo — iterate `await served.all()` (Task 1), **not** the mirror-root listing:
    1. `mirror.ensure(repo, org_id)` — the cron is decoupled from the push path, so it always ensures before building (never assumes a push already did).
    2. `canonical = resolve_canonical_ref(repo, settings.canonical_refs, mirror)` (Task 3); `plan = plan_resolver.resolve(org_id, repo, canonical)` — the canonical ref is passed as the `branch` arg purely to avoid a fake branch; the report path consumes only `plan.telegram_channel` and `plan.language`, never `plan.branch_role`/`is_release`/`is_prerelease`.
    3. `text = await report.build(repo, org_id, lang=plan.language)` — consumes `language` (default `"ru"`; 10.3 later threads non-RU via the localizer). `text is None` (quiet/mirror-only-quiet window) → log and skip (deliver nothing).
    4. `await delivery.deliver(plan, text)` — `DeliveryService` posts when `telegram_channel` resolves, else logs (unmapped org, spec guard).
  - **Per-repo error isolation:** wrap each served repo's iteration (steps 1–4) in `try/except Exception` — log the failing repo/org_id with the exception and `continue` to the next repo. A single repo's failure (a `mirror.ensure` network/auth error, a `LookupError` from `clone_source` on a missing `GITHUB_ORG_LOGINS` entry, an LLM timeout inside `build`) must not starve the other served repos of their report that cadence. This matches the spec's idempotent-re-run guard: a transient per-repo failure is recovered on the next run. Track a failure count and log a run-level summary at the end.
  - Log one structured line per served repo (repo, org_id, delivered vs skipped-empty vs skipped-no-channel vs failed). Idempotent by construction: a re-run in the same window rebuilds and re-delivers the same report — no state is written by this path.
  - `try/finally: await pool.close()`. Runnable as `uv run python -m scripts.report --schedule <name>`.

### Phase 4: Cadences (config + cron)

- [x] **Task 6: Cadence config sample + daily/weekly crons** (depends on Task 5)
  Files: `.env.example`, `deploy/report-crons.crontab`, `Makefile`
  - `.env.example`: add a commented `REPORT_SCHEDULES` example showing the two cadences as config, e.g. `REPORT_SCHEDULES=[{"name":"daily","window":1,"sections":["summary","per_branch","remaining"]},{"name":"weekly","window":7,"sections":["summary"]}]`, with a note that adding/removing a section key here changes the delivered report with no code change (spec verification).
  - `deploy/report-crons.crontab`: two cron entries invoking the entrypoint with distinct `--schedule` names — daily (e.g. `0 8 * * *`) → `uv run python -m scripts.report --schedule daily`; weekly (e.g. `0 8 * * 1`) → `--schedule weekly`. A short header comment notes these are the deployed (prod) crons where Ollama is co-located (no SSH tunnel), and that the `--schedule` values must match `report_schedules` names. (`deploy/` does not exist yet — the file write creates it.)
  - `Makefile`: add convenience targets `report-daily` / `report-weekly` (tunnel prerequisite in dev, mirroring `dev`/`eval`) that run the entrypoint for local exercise, and add both names to the `.PHONY` line (`Makefile:4`).

### Phase 5: Targeted tests (silent-failure surfaces only)

- [x] **Task 7: Tests for the git-range and iteration surfaces** (depends on Task 4)
  Files: `tests/changelog/test_report.py` (or a new `tests/changelog/test_time_window.py`), `tests/commits/` and `tests/ingestion/` as fitting
  Per the project's test-philosophy (test surfaces that fail silently — wrong output, no crash), cover only:
  - `TimeWindow.resolve` over a small temp git repo: an active window returns a `before..after` with the in-window commits; a window older than the last commit resolves to an empty range (`before == after`) so `Report.build` returns `None`; a repo whose whole history is younger than `delta` falls back to `EMPTY_TREE_SHA` for `before`.
  - **Section-interaction test (the review's required crash guard), two cases:** drive `TimeWindow.resolve` → `Report.build` with a real `PerBranchSection` in the section list, asserting `build` returns a report (or `None`) **without raising**, over (a) a temp repo whose entire history is younger than `delta` (`before = EMPTY_TREE_SHA`, real `after`) and (b) an **empty** temp repo with no commits (`before = after = EMPTY_TREE_SHA`, expecting `None`). Both exercise the empty-tree paths through `active_branches`/`commit_timestamp` that an isolated `TimeWindow.resolve` return-value test would miss.
  - `GitCommitCollector.commit_at_or_before`: returns the newest SHA at/before the timestamp, `None` when none qualifies. Add two `active_branches` cases pinning Task 2's fix directly: `before == EMPTY_TREE_SHA` (real `after`) enumerates active branches without raising; `after == EMPTY_TREE_SHA` returns `[]` without raising.
  - `ServedRepoStore.all` ordering/round-trip (if a DB fixture already exists in `tests/ingestion/`; otherwise skip rather than add DB scaffolding).
  - Confirm the existing `tests/changelog/test_schedule.py` (TimeWindow delta-equality, 2-arg `report_for_schedule`) and the `KnowledgeSync`/`CoordinationSeeder`/`EpisodicBackfill` canonical-ref tests still pass unchanged — do not edit them.
