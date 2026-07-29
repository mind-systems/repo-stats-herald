# Test Plan: EpisodicBackfill — store round-trip

## Context
`EpisodicBackfill.run` (`src/episodic/backfill.py`) replays a repo's first-parent history and appends one `EpisodicEntry` per historical step through the injected `EpisodicStore`. This suite drives that end-to-end against a **real `PgEpisodicStore`** (not the in-memory fake used by the git-only suite) to prove the two things an in-memory list cannot: that historical `changed_at` timestamps land as historical and survive a `since`/`until` window read back through SQL, and that a second run over an unchanged repo produces no duplicate rows at the store layer. Per the spec (`.ai-factory/specs/73-episodic-backfill-test-plan.md`, "Store round-trip" group), this is cases 45–46 only; the git-only history-walk / mode-selection cases are the sibling entry and stay out.

## Settings
- Testing: yes
- Logging: minimal
- Docs: no

## Test Command
`uv run pytest tests/episodic/test_backfill_store.py`

## Target Spec File
`tests/episodic/test_backfill_store.py`

## Notes for the implementer
- **Separate module, live Postgres.** These cases require a live database; they must stay in their own module (`test_backfill_store.py`), separate from the git-only behaviour suite (`test_backfill.py`), so that suite keeps running without Postgres. `asyncio_mode = "auto"` — async tests need no marker.
- **Reuse existing fixtures.** `tests/episodic/conftest.py` already provides `pg_pool` (creates/truncates the schema from `src/episodic/schema.sql`), `store` (a `PgEpisodicStore` over that pool), `git_repo` (a fresh `git init -b trunk` repo), and `commit_snapshot` (writes/removes files and commits, pinning both `GIT_AUTHOR_DATE` and `GIT_COMMITTER_DATE` via its `when=` arg). Do not re-invent these.
- **Wire the real backfill.** Assemble `EpisodicBackfill` with a real `GitCommitCollector`, `LinkedChangeResolver`, `AiFactorySourceStrategy`, `CodeSourceStrategy`, and `CodeDistiller`; a fake `RepoMirror` whose `object_store_path` returns the `git_repo` path, whose `ensure`/`default_branch` are trivial, and whose worktree-producing methods (`tree`) raise; a fake `Embedder` returning `[[0.0]*768]`; and a fake `LLMClient`. The default branch the fake mirror reports must match `git_repo`'s branch (`trunk`).
- **Historical timestamps are the point.** Put fixture code under a real source root (`src/…`) so the code strategy actually selects it. Set `when=` on every commit; compare `changed_at` against **tz-aware** `datetime`s (`PgEpisodicStore` returns tz-aware values), never naive ones.
- **Guard — recorded-SHA union.** This suite is the ground-truth check behind the sibling suite's fake store: `PgEpisodicStore.recorded_commit_shas` returns `SELECT DISTINCT unnest(commit_shas)` — the union of *every* `commit_shas` element across all of the repo's entries, which is wider than `run`'s in-memory `recorded.add(after)` top-up. Case 46 exists precisely because the fake store's union must equal this real union; if a re-run duplicated rows, only the real store would reveal it. Assert the duplicate-free invariant by counting rows read back through the store, not by trusting the in-run counters.

## Tasks

### Phase 1: EpisodicBackfill + PgEpisodicStore round-trip

- [x] **Task 1: Windowed query over backfilled history (`run` + `PgEpisodicStore.query`)**
  Files: `tests/episodic/test_backfill_store.py`
  Test cases:
  - `should return only the entries whose historical changed_at falls inside the since/until window when querying a backfilled repo` — build a repo with commits pinned to timestamps straddling the window (one before, one inside, one after via `commit_snapshot(..., when=...)`), run the backfill against `store`, then `store.query(..., repo, since, until)` with a tz-aware window; assert exactly the in-window entry is returned and its `changed_at` equals the historical (not run-moment) timestamp. This is the end-to-end hazard-(c) proof: the window filter is on `changed_at`, so it only passes if backfill wrote the commit's own timestamp.

- [x] **Task 2: No duplicate rows across two runs (`run` + `PgEpisodicStore`)**
  Files: `tests/episodic/test_backfill_store.py`
  Test cases:
  - `should not create duplicate rows when the backfill runs twice over an unchanged repo` — build a small multi-commit repo, call `backfill.run` twice against the same `store`, then read every entry back through `store.query(..., repo, k>=commit count)` and assert the row count equals the number of first-parent commits (one entry per commit, none duplicated). Reading back through the real store — rather than the in-memory list — is what makes this catch a store-layer duplication the git-only idempotency case cannot see.
