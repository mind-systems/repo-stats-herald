# Test Plan: EpisodicWriter

## Context
`EpisodicWriter.write` (`src/ingestion/writer.py`) turns one served `PushEvent` into exactly one appended `EpisodicEntry`; it is straight-line with no branches, so every hazard is *which value lands in which field* — above all a `changed_at` taken from the head commit's git timestamp rather than the ingest wall-clock, which would silently collapse history into "now".

## Settings
- Testing: yes
- Logging: minimal
- Docs: no

## Test Command
`uv run pytest tests/ingestion/test_episodic_writer.py`

## Target Spec File
`tests/ingestion/test_episodic_writer.py`

## Fakes & Fixtures (build once, in a new `tests/ingestion/conftest.py`)

Per spec `.ai-factory/specs/72-episodic-writer-test-plan.md`. Constructor order is `EpisodicWriter(mirror, resolver, embedder, store, collector)` — collector is last, after store; a wrong fixture order surfaces as confusing `AttributeError`s, so wire carefully.

- **`FakeMirror`** — `ensure(repo, org_id)` records calls; `tree(repo, org_id, ref)` is a **synchronous** `@contextlib.contextmanager` yielding a `Path` (use `tmp_path`) and appending `"tree_enter"`/`"tree_exit"` plus its `ref` arg to a shared ordered event log that also records `ensure`. (Sync today; roadmap 20.2.2 / spec 61 makes these awaitable later — behavioral assertions must survive that.)
- **`FakeResolver`** — `resolve(repo_path, before, after)` records args and returns a canned `LinkedChange` (real frozen dataclasses from `src/episodic/linked_change.py` and `src/commits/models.py`, never `Mock`, so field-name typos surface).
- **`FakeCollector`** — only `commit_timestamp(repo_path, ref)` is used; back it with a `dict[ref -> datetime]` returning **timezone-aware** datetimes, so a writer that asks for `push.before` or the wrong path gets a *different, detectable* timestamp.
- **`FakeEmbedder(Embedder)`** — subclass the ABC; `async embed(texts)` appends `texts` to a `calls` list and returns `[[0.1] * 768]`.
- **`FakeStore(EpisodicStore)`** — implement all three abstract methods (`append`, `query`, `recorded_commit_shas`); `append` collects into a list, `query` and `recorded_commit_shas` raise. Never add an update/delete method, or the append-only assertions go vacuous.
- **`make_push` fixture** — builds a `PushEvent` (`src/ingestion/models.py`) whose `PushCommit` messages/SHAs are **deliberately different** from the resolver's `Commit` messages/SHAs, so a source mix-up is decidable.
- `asyncio_mode = "auto"` is set in `pyproject.toml` — async tests need no decorator.

## Tasks

### Phase 1: `changed_at` provenance — the silent-failure core

- [x] **Task 1: `write` — timestamp provenance**
  Files: `tests/ingestion/test_episodic_writer.py`
  Test cases:
  - `should set changed_at to the head commit's timestamp far from now when the push delivers historical commits` — collector returns `datetime(2023, 3, 14, 9, 26, 53, tzinfo=timezone(timedelta(hours=2)))`; assert `entry.changed_at` equals it AND `abs(datetime.now(timezone.utc) - entry.changed_at) > timedelta(days=30)` (the gap assertion is what a `datetime.now()` swap fails)
  - `should read the timestamp for push.after not push.before when the range spans several commits` — collector maps `before -> 2020-01-01`, `after -> 2024-06-01`; assert the recorded call ref is `push.after`
  - `should preserve the commit timestamp tzinfo rather than storing a naive datetime` — assert `entry.changed_at.tzinfo is not None` and the exact offset
  - `should derive changed_at from git not from the push payload` — assert collector called exactly once with `(str(tree_path), push.after)`
  - `should ask the collector for the timestamp against the same worktree path handed to the resolver` — collector returns a sentinel only for the exact yielded tree path; assert that path reached both resolver and collector

### Phase 2: `write` — entry construction / field mapping

- [x] **Task 2: `write` — field mapping onto EpisodicEntry**
  Files: `tests/ingestion/test_episodic_writer.py`
  Test cases:
  - `should append exactly one entry when one push is served`
  - `should copy repo and org_id from the push event when building the entry` — use distinguishable values; assert `org_id` stays an `int`, never the `org_login` string
  - `should set commit_shas from the resolved commits in order when the resolver returns several commits` — resolver SHAs `("aaa","bbb","ccc")` while `PushEvent.commits` carries `("zzz",)`; assert the resolved tuple in order and `"zzz" not in entry.commit_shas`
  - `should set completed_tasks verbatim as a tuple from the resolved change when tasks were completed`
  - `should store the embedder's vector verbatim as the entry embedding` — recognizable vector; assert not truncated, re-normalized, or wrapped
  - `should leave recorded_at unset so the store assigns it server-side` — assert `entry.recorded_at is None`

### Phase 3: `write` — what gets embedded (`content`)

- [x] **Task 3: `write` — content composition and embedding input**
  Files: `tests/ingestion/test_episodic_writer.py`
  Test cases:
  - `should join completed tasks followed by resolved commit messages with newlines when both are present` — assert the exact string, tasks first
  - `should embed the resolver's commit messages not the raw push payload messages when the two differ`
  - `should pass the exact content string as the single embedding input` — assert `embedder.calls == [[entry.content]]`
  - `should call the embedder exactly once per push regardless of how many commits the range contains` — resolver returns 25 commits; assert `len(embedder.calls) == 1`
  - `should include multi-line commit bodies unmodified when a commit message has a subject and body`

### Phase 4: `write` — code-only push and empty ranges

- [x] **Task 4: `write` — code-only and degenerate ranges**
  Files: `tests/ingestion/test_episodic_writer.py`
  Test cases:
  - `should still append an entry with commits and empty completed_tasks when the push completes no roadmap task` — assert one append, `entry.completed_tasks == ()`, and `entry.content` equals just the joined commit messages with no leading newline
  - `should append an entry with empty content when the resolved range yields no tasks and no commits` — `push.before == push.after`, resolver returns empties; assert `entry.content == ""`, `store.append` called once, and the embedder was still called with `[""]` (there is no early-return guard — pin current behavior)

### Phase 5: `write` — append-only / no read-modify-write

- [x] **Task 5: `write` — append-only guarantees**
  Files: `tests/ingestion/test_episodic_writer.py`
  Test cases:
  - `should append two independent entries when two pushes are written in sequence` — assert both retained, order preserved, first entry object unchanged
  - `should never read or query the store while writing` — `FakeStore.query` and `.recorded_commit_shas` raise if called
  - `should not derive or store any narrated outcome field when writing` — assert the appended object is exactly an `EpisodicEntry` and the constructor takes no `Reasoner` (no narration/outcome derivation at write time). Do not assert "no LLM client" — the constructor legitimately takes `embedder: Embedder` (the embedding seam); the invariant is the absence of a `Reasoner` specifically, leaving `embedder` untouched.

### Phase 6: `write` — orchestration order and mirror self-sufficiency

- [x] **Task 6: `write` — orchestration ordering**
  Files: `tests/ingestion/test_episodic_writer.py`
  Test cases:
  - `should call mirror.ensure before opening a worktree when nothing else has refreshed the repo` — assert the ordered event log begins `["ensure", "tree_enter", ...]`
  - `should open the worktree at push.after with the push's repo and org` — assert `mirror.tree` args
  - `should resolve against the worktree path with the push's before/after range` — assert resolver got `str(tree)` (a string, not the `Path`, not the `"org/repo"` name) plus `push.before`/`push.after`
  - `should close the worktree context before embedding and appending` — assert `tree_exit` precedes `embed` and `append` in the event log

### Phase 7: `write` — error propagation (no silent history loss)

- [x] **Task 7: `write` — failures propagate, nothing partial persists**
  Files: `tests/ingestion/test_episodic_writer.py`
  Test cases:
  - `should propagate the exception and append nothing when the embedder fails` — assert no partial entry with a null embedding
  - `should propagate the exception when store.append fails`
  - `should exit the worktree context even when the resolver raises` — assert `tree_exit` still ran
  - `should propagate the exception when the collector cannot read the head commit's timestamp` — `commit_timestamp` raises `subprocess.CalledProcessError`; assert the writer does NOT fall back to `datetime.now()` and appends nothing

## Out of scope (already pinned elsewhere — do not re-test here)
- Set-difference completion semantics, roadmap `[x]` parsing, merge/empty ranges → `tests/episodic/test_linked_change_contract.py` (fake the resolver).
- Cosine ordering, `since`/`until` filtering on `changed_at`, structural append-only at the store → `tests/episodic/test_episodic_store_contract.py` (fake the store).
- Commit-log parsing → `tests/commits/`.

## Gotchas
- Compare aware `changed_at` against `datetime.now(timezone.utc)`, never a naive `datetime.now()` (raises `TypeError`). The column is `timestamptz`; a naive value would be silently reinterpreted.
- The "now" trap needs a wide gap (months/years) — equality with the fake's return alone cannot distinguish a correct read from a wall-clock read.
- `[embedding] = await self._embedder.embed([content])` destructures a one-element list; a 25-commit range with `len(embedder.calls) == 1` catches a per-commit refactor.
- `content` is built only from `change.completed_tasks` and `change.commits.commits[*].message` — never `push.commits`, diffs, paths, authors, or SHAs.
- `FakeStore` must implement all three abstract methods; the two unused ones raising doubles as the "never reads at write time" assertion.
- Mirror is synchronous today — the fake's `tree` is a sync CM used with plain `with`.
