# EpisodicWriter — Test Plan

**Date:** 2026-07-29
**Source:** roadmap-test-coverage agent

## Source Overview

`EpisodicWriter.write` (`src/ingestion/writer.py`) is the bridge from a served `PushEvent` to exactly one appended `EpisodicEntry`: it refreshes the mirror itself, opens a worktree at `push.after`, resolves the push range to a `LinkedChange`, reads the head commit's timestamp, joins tasks + commit messages into `content`, embeds that once, and appends. It is straight-line with no conditionals — every risk lives in *which* value ends up in *which* field, not in branch selection. The layers below it (`LinkedChangeResolver` set-difference semantics, `PgEpisodicStore` SQL/filtering) are already pinned by their own contract suites, so this plan fakes both.

## Instantiation

`EpisodicWriter(mirror, resolver, embedder, store, collector)` — positional order matters and matches `src/main.py`. Constructor type hints are not enforced at runtime, so duck-typed fakes are fine except where an ABC is convenient.

Fakes/mocks needed:

- **`FakeMirror`** — `ensure(repo, org_id)` records calls; `tree(repo, org_id, ref)` is a **synchronous** `@contextlib.contextmanager` yielding a `Path` (use `tmp_path`) and recording enter/exit plus the `ref` it was asked for. It must record ordering relative to `ensure`. (Sync today — roadmap 20.2.2 / spec 61 will make these awaitable; see Gotchas.)
- **`FakeResolver`** — `resolve(repo_path, before, after)` records args and returns a canned `LinkedChange`. Use real frozen dataclasses from `src/episodic/linked_change.py` and `src/commits/models.py`, not Mock objects, so field-name typos surface.
- **`FakeCollector`** — only `commit_timestamp(repo_path, ref)` is used. Back it with a `dict[ref -> datetime]` so a writer that asked for `push.before` (or the wrong repo path) returns a *different, detectable* timestamp rather than the right one by accident. Return **timezone-aware** datetimes (real `commit_timestamp` parses `%cI`, which always carries an offset).
- **`FakeEmbedder(Embedder)`** — `async embed(texts)` appends `texts` to a `calls` list and returns `[[0.1] * 768]`. Subclass the ABC so a signature drift breaks loudly.
- **`FakeStore(EpisodicStore)`** — must implement all three abstract methods (`append`, `query`, `recorded_commit_shas`) to be instantiable; `append` collects entries into a list. It must **not** support update/delete — never add such a method to the fake, or the append-only assertions become vacuous.
- **`make_push` fixture** — builds `PushEvent` from `src/ingestion/models.py`. Critically, give the `PushCommit` payload messages/SHAs that are **different** from the resolver's `Commit` messages/SHAs, so "which source did the writer read" is decidable.
- `asyncio_mode = "auto"` is set in `pyproject.toml` — async tests need no decorator.

Suggested home: `tests/ingestion/test_episodic_writer.py` with a local `conftest.py` (there is none under `tests/ingestion/` today).

## Existing Coverage

- `tests/episodic/test_episodic_store_contract.py` — pins cosine ordering, `since`/`until` filtering on `changed_at` **not** `recorded_at` (the read-side half of the hazard below), and structural append-only. Do not re-test SQL or vector ordering here.
- `tests/episodic/test_linked_change_contract.py` — pins the set-difference completion semantics, relocated/reworded done lines, roadmap path via `SourceStrategy`, commits-only fallback, merge ranges, and empty ranges. Do not re-test roadmap parsing here; fake the resolver.
- Nothing anywhere exercises `EpisodicWriter` (grep hits only `writer.py` and `main.py`). This whole plan is new coverage.

## Test Cases

### `write` — `changed_at` provenance (the silent-failure core)

- **should set `changed_at` to the head commit's timestamp, not the ingest moment, when the push delivers historical commits** — `write`. Setup: `FakeCollector` returns `datetime(2023, 3, 14, 9, 26, 53, tzinfo=timezone(timedelta(hours=2)))` for `push.after`. Assert `entry.changed_at == that exact value` **and** `abs(datetime.now(timezone.utc) - entry.changed_at) > timedelta(days=30)`. The second assertion is the one that fails when someone swaps in `datetime.now()`; the first alone could pass a "now" implementation on a freshly-created fixture repo.
- **should read the timestamp for `push.after`, not `push.before`, when the range spans several commits** — `write` → `collector.commit_timestamp`. Setup: the fake maps `before -> 2020-01-01`, `after -> 2024-06-01`; assert the recorded call arg is `push.after`.
- **should preserve the commit timestamp's tzinfo rather than storing a naive datetime** — `write`. Assert `entry.changed_at.tzinfo is not None` and the offset. A naive datetime reaching `timestamptz` is silently reinterpreted in the session timezone.
- **should derive `changed_at` from git, not from the push payload** — `write`. Documents that the sole source is `collector.commit_timestamp`, asserting `collector` was called exactly once with `(str(tree_path), push.after)`.
- **should ask the collector for the timestamp against the same worktree path handed to the resolver** — `write`. Setup: `FakeCollector` returns a sentinel timestamp only for the exact yielded tree path.

### `write` — entry construction / field mapping

- **should append exactly one entry when one push is served** — `write` → `store.append`.
- **should copy `repo` and `org_id` from the push event when building the entry** — `write`. Use distinguishable values; assert `org_id` stays an `int` (never the `org_login` string).
- **should set `commit_shas` from the resolved commits in order when the resolver returns several commits** — `write`. Setup: resolver returns SHAs `("aaa", "bbb", "ccc")` while `PushEvent.commits` carries `("zzz",)`; assert the resolved tuple, order preserved, and `"zzz" not in entry.commit_shas`.
- **should set `completed_tasks` verbatim from the resolved change when tasks were completed** — `write`. Assert a tuple, not a list or a re-derived set.
- **should store the embedder's vector verbatim as the entry embedding** — `write`. Setup: a recognizable vector; assert not truncated, re-normalized, or wrapped.
- **should leave `recorded_at` unset so the store assigns it server-side** — `write`. Assert `entry.recorded_at is None`. Setting it at write time would make the store's `changed_at`-vs-`recorded_at` distinction meaningless.

### `write` — what gets embedded (`content`)

- **should join completed tasks followed by resolved commit messages with newlines when both are present** — `write`. Assert the exact string, tasks first. Content is what the reasoner later retrieves on; silent reordering or a wrong separator degrades retrieval without any error.
- **should embed the resolver's commit messages, not the raw push payload messages, when the two differ** — `write`. GitHub push payloads truncate at 20 commits, so reading them would silently lose history on large pushes.
- **should pass the exact `content` string as the single embedding input** — `write` → `embedder.embed`. Assert `embedder.calls == [[entry.content]]` — one call, a one-element list, and the same text that is persisted.
- **should call the embedder exactly once per push regardless of how many commits the range contains** — `write`. Setup: resolver returns 25 commits.
- **should include multi-line commit bodies unmodified when a commit message has a subject and body** — `write`.

### `write` — code-only push and empty ranges

- **should still append an entry with commits and empty `completed_tasks` when the push completes no roadmap task** — `write`. Assert one append, `entry.completed_tasks == ()`, and `entry.content` equals just the joined commit messages with **no leading newline**. This is the spec's explicit code-only case.
- **should append an entry with empty content when the resolved range yields no tasks and no commits** — `write`. Setup: `push.before == push.after`, resolver returns empties. Assert `entry.content == ""` and that `store.append` was still called once. There is no early-return guard in the source; pin the actual behavior so a future "skip empty" optimization is a deliberate, visible change. Note the embedder is still called with `[""]`.

### `write` — append-only / no read-modify-write

- **should append two independent entries when two pushes are written in sequence** — `write` twice. Assert both retained, ordering preserved, and the first entry object unchanged.
- **should never read or query the store while writing** — `write`. Setup: `FakeStore.query` and `.recorded_commit_shas` raise if called.
- **should not derive or store any narrated outcome field when writing** — `write`. Assert the appended object is exactly an `EpisodicEntry` and that the constructor takes no `Reasoner`/LLM client. Guards the spec's "write-time stays cheap" rule.

### `write` — orchestration order and mirror self-sufficiency

- **should call `mirror.ensure` before opening a worktree when nothing else has refreshed the repo** — `write`. Assert an ordered event log `["ensure", "tree_enter", ...]`. Pins the docstring's "self-contained — does not rely on `KnowledgeSync` having run first".
- **should open the worktree at `push.after` with the push's repo and org** — `write` → `mirror.tree`.
- **should resolve against the worktree path with the push's before/after range** — `write` → `resolver.resolve`. Assert a string, not the `Path`, and not the `"org/repo"` name.
- **should close the worktree context before embedding and appending** — `write`. Assert `tree_exit` precedes `embed` and `append`. Holding a worktree across a network-bound LLM call is a resource leak that no test would otherwise catch.

### `write` — error propagation (no silent history loss)

- **should propagate the exception and append nothing when the embedder fails** — `write`. Assert no partial entry with a null embedding.
- **should propagate the exception when `store.append` fails** — `write`. An append failure must be visible, never a silently dropped push.
- **should exit the worktree context even when the resolver raises** — `write`. The mirror's deferred-reclamation bookkeeping depends on the generator's `finally` running.
- **should propagate the exception when the collector cannot read the head commit's timestamp** — `write`. Setup: `commit_timestamp` raises `subprocess.CalledProcessError`. Explicitly pin that the writer does **not** fall back to `datetime.now()` — that fallback is the exact silent-history-collapse the hazard describes.

## Gotchas

- **Timezone-aware vs naive datetimes.** `GitCommitCollector.commit_timestamp` uses `%cI` and `datetime.fromisoformat`, so it always yields an **aware** datetime. Fakes must return aware datetimes; comparing an aware `changed_at` against a naive `datetime.now()` raises `TypeError` — use `datetime.now(timezone.utc)`. The column is `timestamptz`, so a naive value would be reinterpreted against the session timezone with no error.
- **The "now" trap needs a wide gap.** Assert the stored timestamp is *far from now* (months/years), not merely "equal to the fake's return". A fixture timestamp close to the current time cannot distinguish the correct implementation from `datetime.now()`.
- **Embedding call count.** `[embedding] = await self._embedder.embed([content])` — a single batched call with a one-element list; the destructuring raises `ValueError` if the embedder returns 0 or ≥2 vectors, so that failure is loud. Assert `len(embedder.calls) == 1` with a 25-commit range to catch a per-commit refactor.
- **Empty commit ranges.** There is no guard: `before == after` with no tasks produces `content == ""`, and the writer still calls `embed([""])` and appends. Pin the writer's behavior with a fake and treat any future skip-empty logic as a spec change.
- **What is embedded.** `content` is built only from `change.completed_tasks` and `change.commits.commits[*].message` — never `push.commits` (the GitHub payload), never diffs, file paths, authors, or SHAs. Give payload and resolved commits deliberately different text so a source mix-up is detectable.
- **Mirror is synchronous today.** `RepoMirror.ensure` / `.tree` are sync (`tree` is a `@contextlib.contextmanager`), so the fake must be a sync CM used with a plain `with`. Roadmap 20.2.2 (`.ai-factory/specs/61-repo-mirror-async-boundary.md`, still `[ ]`) will make them awaitable; when that lands the fakes change shape, and these behavioral assertions should survive unchanged.
- **`FakeStore` must implement all three abstract methods.** Make the two unused ones raise, which doubles as the "never reads at write time" assertion.
- **Don't restate lower layers.** Roadmap `[x]`-parsing, set-difference completion, merge-commit safety, cosine ordering, and `since`/`until` filtering are pinned in `tests/episodic/`; asserting them again through the writer only couples this suite to git and Postgres fixtures it doesn't need.
- **Constructor order is a footgun.** `EpisodicWriter(mirror, resolver, embedder, store, collector)` — the collector is last, after the store. Getting resolver/embedder/store order wrong in a fixture produces confusing `AttributeError`s rather than a clean failure.
