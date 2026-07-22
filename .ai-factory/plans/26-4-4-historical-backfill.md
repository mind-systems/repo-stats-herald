# Plan: 4.4 — Historical backfill

## Context
Replay a served repo's full commit history through the linked-change resolver (4.2), appending one episodic entry per historical commit with the commit's own `changed_at`, so episodic memory can answer "what did we build 6 months ago" for a repo that already existed at deploy time. Resolve + embed only (no per-change LLM generation), idempotent across re-runs.

## Settings
- Testing: no
- Logging: minimal
- Docs: no

## Design notes (read before implementing)

- **Reuse `LinkedChangeResolver.resolve` (4.2) unchanged, per historical step.** `resolve(repo, before, after)` already reads the roadmap at both refs via `git show {ref}:{path}` and collects commits via `git log {before}..{after}` — both work against the **bare object store** (no worktree). Passing the bare repo path plus a `(parent, commit)` pair gives, for that step: the tasks newly `[x]` since the parent (roadmap evaluated at *that* historical tree — early commits predate the roadmap → commits-only; later commits are task-anchored, exactly the per-historical-tree crossover in `docs/concepts/derivation-modes.md`) and the commits the step introduced.
- **The root commit uses the empty-tree SHA (`4b825dc642cb6eb9a060e54bf8d69288fbee4904`) as its `before`.** Verified: `git log <empty-tree>..<root>` lists the root commit, and `git show <empty-tree>:<path>` fails → the resolver reads it as "no prior roadmap" (returns `None`, so every done-marker at root counts as newly completed). This makes every commit — including the root — a uniform `resolve(bare, before, after)` call with no special-casing.
- **No worktree per commit.** Read blobs by SHA against the bare store (`git show`/`git log`/`git rev-list`), satisfying the guard against `git worktree add`/`remove` churn over a long history. This is the deliberate exception to the mirror's worktree-per-operation model, justified by the spec.
- **Idempotency by recorded commit SHA, not a time watermark.** Gather every `commit_shas` value already stored for the repo (covers prior backfill runs *and* live 4.3 pushes) into a set; skip any step whose `after` SHA is already present. A pure `changed_at` watermark breaks when a live push recorded a recent entry before backfill ever ran (it would skip the whole history it must fill) — the SHA set is precise, resumable after interruption, and safe against interleaving with live writes.
- **Mirror the 4.3 writer's map/embed exactly** (`src/ingestion/writer.py`): `content = "\n".join([*completed_tasks, *commit messages])`, embed once, `EpisodicStore.append`. `changed_at = collector.commit_timestamp(bare, after)` — the historical commit's own timestamp, never the run's time.

## Tasks

### Phase 1: Enabling capabilities

- [x] **Task 1: History-walk on `GitCommitCollector`**
  Files: `src/commits/collector.py`
  Add a read-only method that enumerates a ref's first-parent history oldest-first as `(before, after)` SHA pairs, e.g. `first_parent_steps(repo_path: str, ref: str) -> list[tuple[str, str]]`. Implement with `git -C <repo_path> rev-list --reverse --first-parent --parents --end-of-options <ref>` (each output line is `<commit> <parent1> [<parent2> …]`); include `--end-of-options` before the ref to match the sibling methods' convention (`commit_timestamp`, `_collect_commits`) so a ref that looks like an option can't be misinterpreted. For each line, `after = commit`, `before = <first parent>` when present else the empty-tree SHA `4b825dc642cb6eb9a060e54bf8d69288fbee4904` (define it as a module constant with a short comment). Keep the empty-tree constant and all git-command details inside this class (owned-details rule). Read-only. Resolve the error contract explicitly (do **not** copy the siblings' `check=True` blindly — it contradicts a no-crash guarantee): run with `check=False` and return `[]` when `returncode != 0`, so a repo with an unborn `HEAD` (zero commits) or an unknown ref yields `[]` rather than raising `CalledProcessError`. In the Task 4 flow the ref is always the canonical ref resolved *after* `mirror.ensure`, so the non-zero path is only the empty-repo/unknown-ref safety net. This keeps git history-walk details in the commits feature rather than inline in the backfill service.

- [x] **Task 2: Recorded-SHA read on the episodic store**
  Files: `src/episodic/store.py`
  Add an abstract method to `EpisodicStore` and implement it on `PgEpisodicStore`: `async def recorded_commit_shas(self, repo: str) -> set[str]` returning the union of every `commit_shas` element already stored for `repo`. **It must be `async def`** — like the sibling `append`/`query`, `PgEpisodicStore` runs on an asyncpg pool (`async with self._pool.acquire() as conn: await conn.fetch(...)`), so a synchronous signature is impossible and would force callers into an un-awaited coroutine. Implement with a single query that unnests the array, e.g. `SELECT DISTINCT unnest(commit_shas) AS sha FROM episodic_entries WHERE repo = $1`, collected into a `set[str]`. Keep the ABC free of any Postgres concept (matches the existing `append`/`query` split). Used by Task 4 for idempotency.

- [x] **Task 3: Expose the bare object-store path on `RepoMirror`**
  Files: `src/github/mirror.py`
  Add a public accessor returning a repo's bare object store, e.g. `object_store_path(repo: str) -> Path`, delegating to the existing private `_bare_path(repo)`. Document it as the read-only entry point for history replay that intentionally bypasses the worktree-per-operation model (blobs are read by SHA, no mutable checkout). Caller must have run `ensure(repo, …)` first (same precondition as `default_branch`). No behavior change to existing methods.

### Phase 2: The backfill service

- [x] **Task 4: `EpisodicBackfill` service** (depends on Task 1, Task 2, Task 3)
  Files: `src/episodic/backfill.py`
  New `EpisodicBackfill` with constructor DI mirroring `EpisodicWriter`'s collaborators plus a canonical-ref policy: `__init__(self, mirror: RepoMirror, resolver: LinkedChangeResolver, embedder: Embedder, store: EpisodicStore, collector: GitCommitCollector, canonical_refs: dict[str, str])`. It never constructs a concrete client — wired at the composition root (Task 5).

  `async def run(self, repo: str, org_id: int) -> None`:
  1. `self._mirror.ensure(repo, org_id)` (self-contained, like the writer; no reliance on another task having run).
  2. Resolve the canonical ref exactly as `KnowledgeSync._canonical_ref` does: `canonical_refs.get(repo)` else `mirror.default_branch(repo)`.
  3. `bare = str(self._mirror.object_store_path(repo))` (Task 3).
  4. `recorded = await self._store.recorded_commit_shas(repo)` (Task 2, `async def` — **must be awaited**; a missing `await` makes `after in recorded` evaluate `in` against a coroutine and raise `TypeError`) — fetched once up front.
  5. `steps = self._collector.first_parent_steps(bare, canonical)` (Task 1), oldest-first.
  6. For each `(before, after)`:
     - Skip if `after in recorded` (idempotency — already covered by a prior run or a live push).
     - `change = self._resolver.resolve(bare, before, after)` (4.2) — roadmap evaluated at *this* historical tree.
     - Build `content = "\n".join([*change.completed_tasks, *(c.message for c in change.commits.commits)])`, mirroring the 4.3 writer.
     - Skip a step that yields no tasks **and** no commits (empty content) so no empty string is embedded; log at debug. This is defensive — a valid first-parent step's `git log before..after` always yields at least `after`, so it will not fire in normal operation, but it guards against embedding an empty string if a step ever degenerates.
     - `changed_at = self._collector.commit_timestamp(bare, after)` — the historical commit's own timestamp.
     - `[embedding] = await self._embedder.embed([content])` (embed only — this is the sole model call; no generation).
     - Build the `EpisodicEntry` exactly as the writer does (`repo`, `org_id`, `change.completed_tasks`, `commit_shas = tuple(c.sha for c in change.commits.commits)`, `content`, `embedding`, `changed_at`) and `await self._store.append(entry)`.
     - Add `after` to the local `recorded` set so a duplicate `after` within the same run is also skipped.
  7. One summary `logger.info` at the end (repo, commits walked, entries appended, skipped).

  Guards to honor in code: resolve + embed only (no `LLMClient.generate`); `changed_at` is always the historical timestamp; reads the mirror only (no network beyond `mirror.ensure`); `src/episodic/backfill.py` imports only `core`/`llm` infra and the episodic/commits/github public classes it's given — the resolve→map→append flow lives here, matching how 4.3 keeps the bridge out of the store.

### Phase 3: Composition-root entrypoint

- [x] **Task 5: Manual backfill entrypoint** (depends on Task 4)
  Files: `scripts/backfill_episodic.py`
  New composition-root script mirroring `scripts/backfill.py`'s wiring shape (same trigger shape as 3.6's backfill), separate from the knowledge backfill so each has one responsibility. Argparse `--repo` / `--org-id`. In an async `_run`: `get_settings()`, `create_pool(settings.postgres_dsn)`, apply `src/episodic/schema.sql` (read + execute, like `main.py`'s lifespan and `scripts/backfill.py` do for their schemas), then wire concretes exactly as `src/main.py`'s lifespan does for the episodic writer — `OllamaEmbedder`, `PgEpisodicStore`, `AiFactorySourceStrategy`, `GitCommitCollector`, `LinkedChangeResolver(collector, strategy)`, the `GitHubAppAuth` + `clone_source` + `RepoMirror` trio, and `settings.canonical_refs` — then `EpisodicBackfill(mirror, resolver, embedder, store, collector, settings.canonical_refs)` and `await backfill.run(repo, org_id)`. Close the pool in `finally`. Assembly only — no logic in the script beyond wiring (mirror `scripts/backfill.py`'s structure, including the module docstring showing `uv run python -m scripts.backfill_episodic --repo <name> --org-id <id>`).

## Verification (manual, per the spec)
- Backfilling a repo produces episodic entries spanning its full history, each with the correct historical `changed_at` (commits-only for early pre-roadmap commits, task-anchored once the roadmap exists).
- `EpisodicStore.query(embedding, k, repo, since=<old>, until=<older-window-end>)` against a backfilled repo returns only that window's changes (windowed on `changed_at`).
- Re-running the entrypoint on an already-backfilled repo appends no duplicate entries (every step's `after` SHA is already in `recorded_commit_shas`).
