# Test Plan: EpisodicBackfill — history walk and derivation mode

## Context
`EpisodicBackfill` (`src/episodic/backfill.py`) replays a served repo's full first-parent history, choosing per historical step whether to derive from the roadmap (resolver mode) or from changed code blobs (distiller mode), and appending one `EpisodicEntry` per step with that commit's own committer timestamp. Nothing tests it; three silent hazards live there — a mode decided once at HEAD instead of per historical tree, a non-idempotent re-run, and a run-moment timestamp collapsing the history it exists to preserve. Tests drive it against real fixture git repositories so the per-historical-tree contract is exercised, not stubbed away.

## Settings
- Testing: yes
- Logging: minimal
- Docs: no

## Test Command
`uv run pytest tests/episodic/test_backfill.py tests/episodic/test_backfill_store.py`

## Target Spec File
`tests/episodic/test_backfill.py` (git-only behavior suite) and `tests/episodic/test_backfill_store.py` (Postgres round-trip suite).

## Collaborator wiring (grounds every task)
Real, driven against a plain `git init` fixture repo (no bare clone needed — every method shells out with `git -C`):
- `GitCommitCollector` — real; the per-historical-tree contract IS its git behavior.
- `LinkedChangeResolver(GitCommitCollector(), AiFactorySourceStrategy())` — real; the `[ ]→[x]` set-difference per step is the subject.
- `AiFactorySourceStrategy()` in the `source_strategy` slot; `CodeSourceStrategy()` in the `code_strategy` slot — real pure predicates. Note the two are adjacent and same-typed; swapping them runs silently, so case 22 guards the order.
- `CodeDistiller` — real, wrapping a **fake `LLMClient`** that records every prompt so per-step prompt counts and blob-body presence are observable.
- `Embedder` — fake: returns `[[0.0]*768]`, records every `texts` argument.
- `RepoMirror` — fake exposing only `ensure(repo, org_id)`, `object_store_path(repo) -> Path`, `default_branch(repo) -> str`; records call order and **raises from every worktree-producing method** so "no worktree per step" is enforced structurally. `object_store_path` returns the fixture repo path.
- `EpisodicStore` — fake in-memory (behavior suite): `append` pushes to a list; `recorded_commit_shas` returns the real **union** of every stored entry's `commit_shas` (narrower in-run set vs. store read-back is exactly what idempotency must survive). `PgEpisodicStore` via the existing `pg_pool` fixture for the round-trip suite only.

Fixtures: extend `tests/commits/conftest.py::_commit` (sets **both** `GIT_AUTHOR_DATE` and `GIT_COMMITTER_DATE`) and the roadmap/merge builders in `tests/episodic/conftest.py`. `asyncio_mode = "auto"` — async tests need no marker. Put all fixture source code under `src/` with a listed extension, or `CodeSourceStrategy` selects nothing.

## Tasks

### Phase 1: EpisodicBackfill._canonical_ref — ref selection

- [ ] **Task 1: `_canonical_ref` — override vs. default branch**
  Files: `tests/episodic/test_backfill.py`
  Test cases:
  - `should walk the configured override ref when canonical_refs holds an entry for the repo` — build two branches with different commits, make `default_branch` return the other one, assert the override branch was walked
  - `should fall back to the mirror's default branch when canonical_refs has no entry for the repo`

### Phase 2: EpisodicBackfill._harness_present — mode boundary

- [ ] **Task 2: `_harness_present` — crossover and edges**
  Files: `tests/episodic/test_backfill.py`
  Test cases:
  - `should return True when the roadmap exists at after only` (introducing step is artifact-mode — pins the crossover)
  - `should return True when the roadmap exists at before only` (roadmap-deleting step stays artifact-mode)
  - `should return False when neither end of the step has any roadmap candidate`
  - `should return True for .ai-factory/ROADMAP.md when the root ROADMAP.md never existed`
  - `should return False for every step when a strategy with empty roadmap_paths() is injected as source_strategy` (pass `CodeSourceStrategy()` in the `source_strategy` slot — guards the argument-order footgun)
  - `should return True for a roadmap file with no [x] lines and still append a commits-only entry` (presence, not content, selects the mode)
  - `should return False when a similarly-named non-candidate path exists` (write `docs/ROADMAP.md`; it must not flip the mode)

### Phase 3: EpisodicBackfill._resolve_entry — resolver mode

- [ ] **Task 3: `_resolve_entry` — resolver-mode entry construction**
  Files: `tests/episodic/test_backfill.py`
  Fixture notes: done lines must carry a **dotted** task id (e.g. `- [x] 1.1 — …`) — the resolver keys `completed_tasks` on `\d+(?:\.\d+)+`, so a bare `- [x] 1` or `- [x] Task one` yields an empty set and the transition/ordering cases pass vacuously. Assert the entry's `repo` field (from `run`'s own argument), **not** `change.repo` — `_resolve_entry` passes the bare filesystem path as the resolver's `repo` arg, so `change.repo` is a path, not the repo name.
  Test cases:
  - `should set changed_at to the historical commit's committer timestamp not the run moment` (pin the fixture commit via both date env vars; assert equality against a tz-aware datetime AND assert `changed_at.year != datetime.now().year`)
  - `should set completed_tasks to only that step's [ ]->[x] transitions` (a task already `[x]` at `before` that merely relocates must not reappear)
  - `should build content as the completed tasks followed by the range's commit messages` (assert ordering — `content` is what gets embedded)
  - `should set commit_shas to every commit in the before..after range` (on a merge step including side-branch commits)
  - `should return None and skip the step when the range yields neither tasks nor message text` (only reachable via `git commit --allow-empty --allow-empty-message -m ""`)
  - `should embed the entry's content as a single-element batch`
  - `should never call the distiller or the LLM in resolver mode`

### Phase 4: EpisodicBackfill._distill_entry — code-derived mode

- [ ] **Task 4: `_distill_entry` — selection and temp-tree materialization**
  Files: `tests/episodic/test_backfill.py`
  Test cases:
  - `should pass only the step's changed code-selected paths to the distiller not the whole tree`
  - `should exclude non-code paths from the distiller input`
  - `should write each selected blob at the after ref into a temp tree the distiller can actually read` (fake `LLMClient` asserts the file's body text appears in the prompt — proves the await happens inside the `TemporaryDirectory` scope)
  - `should issue one prompt per touched module rather than one prompt for the whole step` (real `CodeDistiller.group_units`)
  - `should skip a path deleted in the step and still distill the remaining paths`
  - `should skip a non-UTF-8 blob and still produce an entry from the remaining paths` (commit `src/bin.py` with invalid UTF-8 bytes written directly)
  - `should recreate nested directories in the temp tree for a nested source path`
  - `should treat every path as added for the root commit` (`before == EMPTY_TREE_SHA`)
  - `should leave no temp directory behind after a step` (redirect the temp base to a `tmp_path` subdir, assert it's empty afterwards — use `monkeypatch.setattr(tempfile, "tempdir", str(subdir))`, not `setenv("TMPDIR", ...)` alone: `gettempdir()` caches into `tempfile.tempdir` on first use, so the env var may not take effect if `tempfile` was already initialized this session)

- [ ] **Task 5: `_distill_entry` — fallbacks and timestamp**
  Files: `tests/episodic/test_backfill.py`
  Test cases:
  - `should fall back to the range's commit messages and issue zero LLM calls when no code path was selected`
  - `should fall back to the commit messages when the distiller returns only whitespace` (the `.strip()` -> `""` -> `distilled or ...` fallback)
  - `should return None and skip when there is neither distilled text nor any commit message`
  - `should set completed_tasks to () and changed_at to the historical commit timestamp in code-derived mode` (the hazard-c assertion on the code path — a fix applied to only one path is silent for half the timeline)

### Phase 5: EpisodicBackfill.run — mode selection across a mixed history

- [ ] **Task 6: `run` — walk and per-step mode selection**
  Files: `tests/episodic/test_backfill.py`
  Test cases:
  - `should append one entry per first-parent commit including the root commit when backfilling an N-commit repo` (root step's `before` is `EMPTY_TREE_SHA`)
  - `should derive early entries from code and later entries from the resolver when the repo acquires a roadmap mid-history` (mixed-history fixture: commits 1–2 touch only `src/*.py`; commit 3 adds `ROADMAP.md` with a `- [x] 1.1` line; commits 4–5 flip more boxes; assert the exact split — 2 code-derived, 3 artifact-derived — and that the mode flips exactly once at the transition, on the entry list sorted by `changed_at`)
  - `should invoke the LLM only for pre-roadmap steps and never for post-roadmap steps when HEAD carries a roadmap` (anti-HEAD assertion: a once-at-tip evaluation would make LLM count 0 and fail this)
  - `should derive every entry from code when no commit in the whole history ever carried a roadmap`
  - `should derive every entry through the resolver with zero LLM calls when a roadmap exists at the very first commit` (assert `fake_llm.prompts == []` across the whole history)
  - `should walk only first-parent history when a side branch was merged` (one entry for the merge step whose `commit_shas` includes the side commits; no standalone entry keyed on a side commit)

- [ ] **Task 7: `run` — idempotency, guards, and logging**
  Files: `tests/episodic/test_backfill.py`
  Test cases:
  - `should append nothing and issue no embed or LLM call on a second run over an unchanged repo` (reuse the same store instance; snapshot entry count, `embedder.calls`, `llm.prompts` after run 1 and assert all three identical after run 2)
  - `should append only the entries for commits added since the last run when new commits land between runs`
  - `should skip a step whose after SHA was already recorded by a live push rather than by a prior backfill` (pre-seed the store with one entry whose `commit_shas` contains a mid-history SHA)
  - `should call mirror.ensure before reading the object store path`
  - `should never request a worktree for any historical step` (fake mirror's worktree entry points raise)
  - `should complete without raising and append nothing when the canonical ref does not exist in the mirror` (`first_parent_steps` returns `[]`)
  - `should append nothing for a repo with an unborn HEAD` (`git init` with zero commits)
  - `should log commits_walked / entries_appended / skipped consistent with the store contents` (via `caplog`; a `None`-returning step lands in `skipped`, not `appended`)
  - `should embed exactly once per appended entry and never for a skipped step`

### Phase 6: Store round-trip (Postgres — uses the existing `pg_pool` fixture)

- [ ] **Task 8: `run` + `PgEpisodicStore` — windowed query and no duplicate rows**
  Files: `tests/episodic/test_backfill_store.py`
  Test cases:
  - `should return only the entries inside the window when querying a backfilled repo with since/until` (only meaningful because `changed_at` is historical — doubles as an end-to-end hazard-c check)
  - `should not create duplicate rows across two runs` (the in-memory idempotency test cannot catch store-layer duplication)
