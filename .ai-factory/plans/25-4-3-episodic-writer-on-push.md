# Plan: 4.3 — Episodic writer on push

## Context
On a served push, resolve the push's `LinkedChange` (4.2), map it into an `EpisodicEntry`, embed its `content`, and append it to the `EpisodicStore` (4.1) — so a live push finally produces the episodic history the store was built to hold. This wires the last missing link in Phase 4's write path; the *outcome* stays a read-time concern of the reasoner.

## Grounding notes / assumptions (read before implementing)
- **The resolver already lives in `src/episodic/`.** 4.2.2 shipped `LinkedChangeResolver` in `src/episodic/linked_change.py`, and there is **no** `src/changelog/` module. `LinkedChange.resolve(repo, before, after)` takes plain strings, so `src/episodic/` is currently push-agnostic — it knows only `EpisodicEntry` and the resolver's string surface.
- **The orchestrator lives in the push layer, NOT in `src/episodic/`.** Spec 25's Guard (line 23) is explicit: *"`src/episodic/` itself never imports `src/changelog/` or anything push-shaped — it only knows `EpisodicEntry`."* An orchestrator that imports `PushEvent` and takes `write(self, push: PushEvent)` is push-shaped, so it must **not** live under `src/episodic/`. This is a governing-spec guard, not a stale description, so it cannot be overridden by placing the class in episodic. Resolution: put `EpisodicWriter` in `src/ingestion/writer.py` — the push feature already owns `PushEvent` — and let it depend on episodic's **public** classes (`EpisodicStore`, `EpisodicEntry`, `LinkedChangeResolver`). ARCHITECTURE explicitly permits this: "if feature B needs feature A, it depends on A's public class." `src/episodic/` then keeps knowing only `EpisodicEntry`; the router stays thin (delegates to a background task, no resolve/embed/append logic in its body); and the guard holds literally.
  - The `KnowledgeSync`-in-`src/knowledge/sync.py` precedent is **not** transplantable here: the knowledge spec carries no "never anything push-shaped" clause, whereas the episodic spec deliberately does. The asymmetry is intentional, so the placement differs by design.
- **`completed_tasks` are task identifiers, not titles.** `LinkedChange.completed_tasks` holds stable identifiers (e.g. `"4.2.1"`) extracted by the resolver, not full titles. The spec's "completed task titles" describes intent; `content` uses the identifiers that actually exist plus the commit messages.
- **`resolve` and the commit collector take a git repo *path*, not a repo name.** `LinkedChangeResolver.resolve(repo, before, after)` shells `git -C <repo> …`; pass a mirror worktree path (from `RepoMirror.tree`), whose shared object store makes `before..after` and `before:path` reachable.
- **Episodic schema is not applied yet.** `src/main.py`'s lifespan applies the ingestion and knowledge schemas but not `src/episodic/schema.sql`; this task must add it, or `append` fails at runtime.
- **No branch gate.** Unlike 3.6's semantic sync (canonical-ref only), the episodic log records every served push (Phase 4: "records everything that happened, not only feature completions"). The writer runs for any served push, after the allowlist check.
- **Zero-SHA first push edge.** GitHub sends `before = "0"*40` for a brand-new branch. `resolve` calls `GitCommitCollector.collect(repo, "000…..after")`, and `git log 000…..after` errors → the background task raises (visible, per the guard "a failure to append raises, never silently drops history"). This is the resolver's contract surface (4.2), out of scope to fix here; flag it during verification and, if it must be handled, raise it as a 4.2 follow-up rather than patching the writer.

## Settings
- Testing: no
- Logging: minimal
- Docs: no

## Tasks

### Phase 1: Episodic write path

- [x] **Task 1: Add head-commit timestamp reader to `GitCommitCollector`**
  Files: `src/commits/collector.py`
  Add a method `commit_timestamp(self, repo_path: str, ref: str) -> datetime` that shells `git -C <repo_path> show -s --format=%cI --end-of-options <ref>` (committer date, strict ISO-8601) and returns an aware `datetime` via `datetime.fromisoformat(result.stdout.strip())`. **`.strip()` is required** — `subprocess.run(..., text=True).stdout` carries a trailing `\n`, and `fromisoformat` raises `ValueError` on it (mirror the existing `_current_branch`, which already strips). Keep the git-command detail inside the collector (encapsulation, mirroring `_collect_commits`). Use `from datetime import datetime` (the class, matching `src/episodic/models.py:2` — a bare `import datetime` would make `datetime.fromisoformat` an `AttributeError`); `subprocess.run(..., check=True, capture_output=True, text=True)` consistent with the existing methods.

- [x] **Task 2: Add `EpisodicWriter` orchestrator in the push layer** (depends on Task 1)
  Files: `src/ingestion/writer.py` (new — in `src/ingestion/`, NOT `src/episodic/`, per grounding note 2)
  New class `EpisodicWriter` with constructor DI — takes `RepoMirror`, `LinkedChangeResolver`, `Embedder`, `EpisodicStore`, and `GitCommitCollector` (all abstractions/collaborators, no concrete construction inside). Single public coroutine `async def write(self, push: PushEvent) -> None`:
  1. `self._mirror.ensure(push.repo, push.org_id)` (idempotent fetch; makes the writer self-contained rather than depending on `KnowledgeSync.on_push` having run first).
  2. `with self._mirror.tree(push.repo, push.org_id, push.after) as tree:` → `change = self._resolver.resolve(str(tree), push.before, push.after)` and `changed_at = self._collector.commit_timestamp(str(tree), push.after)` (both sync, inside the tree context).
  3. Build `content` = the completed-task identifiers followed by each commit message, joined by newlines: `"\n".join([*change.completed_tasks, *(c.message for c in change.commits.commits)])`.
  4. `[embedding] = await self._embedder.embed([content])`.
  5. Construct `EpisodicEntry(repo=push.repo, org_id=push.org_id, completed_tasks=change.completed_tasks, commit_shas=tuple(c.sha for c in change.commits.commits), content=content, embedding=embedding, changed_at=changed_at)` and `await self._store.append(entry)`.
  6. `logger.info(...)` one line on completion (repo, counts of tasks/commits), mirroring `KnowledgeSync`'s logging style.
  Imports (all of episodic's **public** classes plus infra): `PushEvent` from `src.ingestion.models`, `EpisodicEntry` from `src.episodic.models`, `EpisodicStore` from `src.episodic.store`, `LinkedChangeResolver` from `src.episodic.linked_change`, `Embedder` from `src.llm.embedder`, `GitCommitCollector` from `src.commits.collector`, `RepoMirror` from `src.github.mirror`. Do **not** derive or store any narrated outcome (write-path stays cheap: exactly one `embed` call, no `LLMClient.generate`).

### Phase 2: Composition + routing

- [x] **Task 3: Apply episodic schema and wire `EpisodicWriter` at the composition root** (depends on Task 2)
  Files: `src/main.py`
  - Add `EPISODIC_SCHEMA_PATH = Path(__file__).resolve().parent / "episodic" / "schema.sql"` and execute it in the lifespan's `pool.acquire()` block alongside the existing `SCHEMA_PATH` / `KNOWLEDGE_SCHEMA_PATH` executions (unconditional, so `episodic_entries` exists before any append, even when the writer is disabled; `CREATE TABLE IF NOT EXISTS`, so idempotent).
  - Inside the existing gated block (the one that builds `mirror`, `embedder`, `strategy`, `indexer`, `KnowledgeSync`), construct: `PgEpisodicStore(pool)` bound to a distinct local name (e.g. `episodic_store` — `store` is already `PgVectorStore` at `main.py:42`), `GitCommitCollector()`, `LinkedChangeResolver(collector, strategy)` (reuse the same `strategy` and `embedder` already built there), then `EpisodicWriter(mirror, resolver, embedder, episodic_store, collector)` and assign `app.state.episodic_writer = ...`. Import `PgEpisodicStore` from `src.episodic.store`, `EpisodicWriter` from `src.ingestion.writer`, `LinkedChangeResolver` from `src.episodic.linked_change`, `GitCommitCollector` from `src.commits.collector`.

- [x] **Task 4: Invoke the episodic writer from the push handler** (depends on Task 3)
  Files: `src/ingestion/router.py`
  In `receive_github_webhook`, inside the `event_name == "push"` branch, **after** the existing `knowledge_sync` background-task registration (so it runs after the semantic sync), add:
  ```python
  episodic_writer = getattr(request.app.state, "episodic_writer", None)
  if episodic_writer is not None:
      background_tasks.add_task(episodic_writer.write, event)
  ```
  Use `getattr(..., None)` exactly like the `knowledge_sync` guard so the webhook contract tests (which run without lifespan, so `app.state` is unset) still return 200 and are unaffected. Do not add any resolve/embed/append logic inline in the router — it only registers the delegating background task.

## Verification (manual / behavioral — per the spec)
- A served push completing a roadmap task → one `EpisodicEntry` for the repo with that task identifier in `completed_tasks`, the range's commit SHAs in `commit_shas`, `changed_at` = the `after` commit's committer timestamp, and a populated `embedding`.
- A code-only push (no roadmap done-transition) → one entry with `completed_tasks` empty and commits populated.
- Two consecutive pushes → two retained entries in order (append-only; nothing overwritten).
- The webhook contract test suite (`tests/ingestion/test_webhook_contract.py`) still passes unchanged.

## Deferred observation (out of scope — noted for later)
- On every served push both `KnowledgeSync.on_push` and `EpisodicWriter.write` independently call `mirror.ensure` (a `git fetch --prune`) and open a worktree at `push.after`. This double-fetch is an inherent, acceptable cost of the self-contained design; if push volume grows it is the natural candidate for a shared per-push mirror-refresh step upstream of both background tasks.
