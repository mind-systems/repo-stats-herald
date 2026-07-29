## Plan Review Summary

**Plan:** `.ai-factory/plans/72-episodicbackfill-store-round-trip.md`
**Artifacts Reviewed:** plan + governing spec (`.ai-factory/specs/73-episodic-backfill-test-plan.md`) + target source (`src/episodic/backfill.py`, `src/episodic/store.py`, `src/episodic/schema.sql`), shared fixtures (`tests/episodic/conftest.py`), and the sibling git-only suite (`tests/episodic/test_backfill.py`)
**Risk Level:** 🟢 Low

### Context Gates
- **Roadmap (`.ai-factory/ROADMAP_TESTS.md`):** ✅ Linked. The plan heading maps to the `[ ]` line 22 — *"EpisodicBackfill — store round-trip"* — whose `Spec:` tag points to spec 73, the exact spec the plan cites. The plan correctly scopes to that entry's "store round-trip group only" and defers the git-only history-walk cases to the already-shipped sibling entry (line 21, `[x]`). No linkage gap.
- **Architecture (`.ai-factory/ARCHITECTURE.md`):** ✅ No boundary concern. The plan wires concretes only inside the test's own composition-root helper (matching the sibling suite's `make_backfill`), keeps the Postgres-dependent cases in their own module so the git-only suite still runs without a database, and touches no feature-to-feature import. Consistent with the feature-modular pattern.
- **Rules:** No `.ai-factory/RULES.md`-level violation observed; `asyncio_mode = "auto"` handling and the live-Postgres-in-a-separate-module convention match the existing `test_episodic_store_contract.py` approach.

### Critical Issues
None.

### Assumptions Verified Against Ground Truth
Every codebase claim the plan makes was checked and holds:
- **Fixtures reused, not re-invented** — `pg_pool`, `store`, `git_repo` (`git init -b trunk`), and `commit_snapshot` (pins both `GIT_AUTHOR_DATE`/`GIT_COMMITTER_DATE` via `when=`) all exist in `tests/episodic/conftest.py` exactly as described.
- **Constructor arg order** — `EpisodicBackfill(mirror, resolver, embedder, store, collector, canonical_refs, distiller, code_strategy, source_strategy)` matches `backfill.py` and `scripts/backfill_episodic.py`. The plan preserves the `code_strategy`-then-`source_strategy` ordering, the documented same-typed footgun.
- **`default_branch` must be `trunk`** — correct; the shared `git_repo` fixture initializes on `trunk`, and the plan's fake mirror reports it.
- **`recorded_commit_shas`** — the plan's description ("`SELECT DISTINCT unnest(commit_shas)`, the union across all entries, wider than `run`'s in-memory `recorded.add(after)` top-up") matches `PgEpisodicStore.recorded_commit_shas` verbatim, and the reasoning for why case 46 needs the *real* store is sound.
- **`query` filters on `changed_at`** — confirmed: `since`/`until` bind `changed_at >= / <=`, so the windowed-query test genuinely doubles as the end-to-end historical-timestamp proof, as the plan claims.
- **tz-aware comparison** — `schema.sql` declares `changed_at timestamptz NOT NULL`, so asyncpg returns tz-aware values; the plan's instruction to compare only against tz-aware `datetime`s is correct and prevents the naive/aware `TypeError`.
- **`k >= commit count`** — the plan explicitly sizes the read-back `k` at/above the commit count in Task 2. This is the right guard: the query's `ORDER BY embedding <=> $q` over identical zero vectors yields undefined ordering, so only a `LIMIT` at least as large as the row set guarantees the count assertion is not truncated. Good foresight.
- **No migration needed** — `episodic_entries` schema already ships (Phase 4.1.1); the `pg_pool` fixture applies and truncates it. Nothing new to create.

### Positive Notes
- The two tasks target exactly the two invariants an in-memory list cannot prove — historical `changed_at` surviving a SQL `since`/`until` window, and store-layer row de-duplication across re-runs — and the plan articulates *why* each is uncatchable by the sibling suite, not just *what* to assert.
- The "Notes for the implementer" section is precise about the fake surface (`object_store_path` → `git_repo`, `tree` raises, embedder returns `[[0.0]*768]`) and reuses the established fixtures rather than inventing parallel ones, keeping the two suites consistent.
- Fixture-code-under-`src/` guidance is carried forward correctly — `CodeSourceStrategy` requires a `src/…`-rooted path with a listed extension, so the commits in both cases will actually be code-selected rather than silently falling back.

PLAN_REVIEW_PASS
