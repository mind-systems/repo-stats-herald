# Test Plan: KnowledgeSync canonical-ref gate

## Context
`KnowledgeSync` (`src/knowledge/sync.py`) is the only writer keeping a served repo's semantic memory equal to "what the project is now." Its canonical-ref gate is the sole thing stopping a feature-branch push from silently overwriting that answer, so this plan pins the gate in both directions plus changed-path derivation, tree pinning at the push SHA, removal of curated paths, and both `backfill` walks.

## Settings
- Testing: yes
- Logging: minimal
- Docs: no

## Test Command
`uv run pytest tests/knowledge/test_knowledge_sync.py`

## Target Spec File
`tests/knowledge/test_knowledge_sync.py`

## Fixture Notes (for the implementer)
- **`KnowledgeSync(mirror, indexer, strategy, canonical_refs, seeder=None)`** — all five collaborators are constructor-injected; nothing is built internally, so no module patching is needed. Pass fakes with `# type: ignore[arg-type]`, matching the seeder-test convention.
- **Fake `RepoMirror`** — model on `_FakeMirror` in `tests/graph/test_coordination_seeder.py`. Only `ensure(repo, org_id)`, `default_branch(repo)`, and `tree(repo, org_id, ref)` are touched. `tree` MUST be a **sync** `@contextmanager` (an `@asynccontextmanager` fake fails with an unrelated `AttributeError`). Materialize a `{relative_path: content}` dict into a `TemporaryDirectory` and yield the `Path`. Extend it to record every `ensure` and `tree` call as `(repo, org_id, ref)` tuples — gate tests assert `tree` was *not* called.
- **Fake `ArtifactIndexer`** — `async def index(repo, path, tree)` and `async def remove(repo, path)`, each appending to a list; record `tree` too for the push-SHA case. A raising variant covers the error path. (`async def` is mandatory — a plain `Mock` returns a non-awaitable and blows up at `await`.)
- **`strategy`** — use the real `AiFactorySourceStrategy` for realism; for the "never consulted" case use a tiny stub `SourceStrategy` whose `selects` records its arguments.
- **`canonical_refs`** — a plain dict. `{}` exercises the default-branch fallback; `{"repo": "release"}` exercises the override. Prefer a fake `default_branch` returning something other than `"main"` (e.g. `"trunk"`) so a hardcoded-`"main"` regression cannot pass.
- **`seeder`** — optional fake `CoordinationSeeder` with `async def seed(repo, org_id)` recording calls; also cover `None` explicitly.
- **Integration cases (12, 30)** — real `ArtifactIndexer` + stub `Embedder` returning fixed-dim (768) vectors + a recording/in-memory `KnowledgeStore` keyed `(repo, path)`. Assert at the store boundary. Do not reuse `tests/knowledge/conftest.py`'s Postgres `pg_pool`/`store` unless a case explicitly needs a live database.
- `asyncio_mode = "auto"` is set, so `async def test_*` needs no marker.
- **Assert sets, never call order.** Changed-path collection is a `set` with nondeterministic iteration; only relative ordering between phases (all indexing before `seed`) is guaranteed — use a shared call log for that.

## Tasks

### Phase 1: on_push — the canonical-ref gate

- [x] **Task 1: on_push suppresses all semantic work on a non-canonical push**
  Files: `tests/knowledge/test_knowledge_sync.py`
  Test cases:
  - `should perform no indexing, no removal, and open no mirror tree when the push branch is not the canonical ref` (canonical_refs={"repo": "main"}, push branch="feature/x" whose commits add/modify/remove curated paths — `docs/a.md`, `.ai-factory/specs/1.md`, `ROADMAP.md`; assert index==[], remove==[], zero recorded `tree` calls — the inversion detector)
  - `should not consult the source strategy at all when the push branch is not the canonical ref` (stub strategy recording `selects`; push removes a curated path; assert `selects` never called)
  - `should not invoke the coordination seeder when the push branch is not the canonical ref` (assert `seeder.seed` calls == [])
  - `should still ensure the mirror before deciding on a non-canonical push` (assert `mirror.ensure` called exactly once with `(push.repo, push.org_id)` even though nothing else ran)

- [x] **Task 2: on_push canonical-ref resolution, both directions**
  Files: `tests/knowledge/test_knowledge_sync.py`
  Test cases:
  - `should index changed paths when the push branch equals the canonical ref` (same push as Task 1 but branch="main" — the positive half of the gate)
  - `should gate on the resolved override rather than the mirror default branch when canonical_refs names the repo` (default_branch returns "main", canonical_refs={"repo": "release"}; push on "release" indexes, push on "main" does nothing)
  - `should gate on the mirror default branch when canonical_refs has no entry for the repo` (canonical_refs={} or an entry for a *different* repo to catch a wrong-key lookup; default_branch returns "trunk"; push on "trunk" indexes, push on "main" does not)

### Phase 2: on_push — changed-path derivation

- [x] **Task 3: changed-set derivation across commits and buckets**
  Files: `tests/knowledge/test_knowledge_sync.py`
  Test cases:
  - `should derive the changed set as the union of added, modified, and removed across every commit in the push` (three commits, each a distinct path in a distinct bucket, plus one path repeated across two commits; assert recorded paths as a **set**; assert the duplicated path produced exactly one call)
  - `should index a path that exists in the tree at push.after regardless of which bucket a commit listed it in` (path listed under `removed` in an early commit but re-added and present in the tree; assert indexed, not removed — last-writer-wins on tree existence)
  - `should complete without indexing or removing anything when the canonical push carries no commits` (commits=(); assert no index/remove calls and that the seeder still ran — a zero-commit canonical push is still a canonical-ref state change)

- [x] **Task 4: removal branch is tree-existence- and strategy-guarded**
  Files: `tests/knowledge/test_knowledge_sync.py`
  Test cases:
  - `should delete a removed curated path from the store when it is absent from the tree` (assert `indexer.remove(repo, "docs/gone.md")` called and `index` not)
  - `should not call remove for a non-curated path that is absent from the tree` (commit removes `src/deleted.py`, real `AiFactorySourceStrategy`; assert `remove` calls == [])
  - `should treat a modified path that is missing from the tree as a removal when it is curated` (modified=("docs/x.md",) but tree at push.after lacks it — force-push/rewritten history; assert it is removed)

- [x] **Task 5: non-curated code paths are handed to the indexer but stored at neither boundary (integration)**
  Files: `tests/knowledge/test_knowledge_sync.py`
  Test cases:
  - `should open the tree but store nothing when the canonical push touches only non-curated code paths` (real `ArtifactIndexer` with stub embedder + recording store; note `KnowledgeSync` *does* call `indexer.index` for these — filtering lives inside `ArtifactIndexer.index`; assert at the **store** boundary, not the `index` boundary)

### Phase 3: on_push — tree pinning and fan-out

- [x] **Task 6: the tree is opened at push.after and its path reaches the indexer**
  Files: `tests/knowledge/test_knowledge_sync.py`
  Test cases:
  - `should open the mirror tree at push.after rather than at the canonical ref name` (fake mirror records `tree` args; push branch="main", after="deadbeef"; assert recorded ref == "deadbeef")
  - `should pass the yielded tree path to the indexer for every indexed file` (indexer records its `tree` argument; assert it equals the path the fake yielded)

- [x] **Task 7: seeder fan-out ordering, optionality, and failure release**
  Files: `tests/knowledge/test_knowledge_sync.py`
  Test cases:
  - `should invoke the coordination seeder once after indexing on a canonical push` (shared call log; assert `seed` recorded after the last `index`)
  - `should complete normally when no seeder was injected` (seeder=None)
  - `should propagate an indexer failure and still release the mirror tree` (indexer raises on a chosen path; assert the exception surfaces and the fake `tree` context manager ran its `finally`)

### Phase 4: backfill — the tree walk

- [x] **Task 8: backfill indexes every non-.git file with repo-relative POSIX paths**
  Files: `tests/knowledge/test_knowledge_sync.py`
  Test cases:
  - `should index every non-.git file in the tree at the canonical ref` (assert recorded index paths as a **set** equal all files — backfill does not pre-filter; selection is the indexer's job)
  - `should pass repo-relative POSIX paths to the indexer rather than absolute paths` (nested file `docs/nested/deep/a.md`; assert the exact relative POSIX string)
  - `should skip everything under a .git directory while passing dotfiles through` (include `.git/config`, and sibling `docs/.gitignore` + `.gitkeep`; assert the `.git/*` file is skipped but the dotfiles *are* indexed — guards against a `startswith(".git")` regression)
  - `should index only files and skip directories` (tree with nested directories; assert no directory path was passed to the indexer)
  - `should complete without error and index nothing when the tree is empty`

- [x] **Task 9: backfill canonical-ref resolution and ensure ordering**
  Files: `tests/knowledge/test_knowledge_sync.py`
  Test cases:
  - `should open the tree at the canonical ref resolved from canonical_refs when an override exists` (canonical_refs={"repo": "release"}; assert recorded `tree` ref == "release" and `default_branch` never consulted)
  - `should open the tree at the mirror default branch when canonical_refs has no entry` (fake `default_branch` returns "trunk"; assert recorded `tree` ref == "trunk")
  - `should ensure the mirror before resolving the canonical ref` (fake whose `default_branch` raises unless `ensure` has already run; assert backfill completes — locks the ordering a call-count assertion would miss)

- [x] **Task 10: backfill fan-out, idempotency, and failure release**
  Files: `tests/knowledge/test_knowledge_sync.py`
  Test cases:
  - `should invoke the coordination seeder once after the walk completes` (shared call log; assert `seed` recorded after the last `index`)
  - `should complete without a seeder when none was injected` (seeder=None)
  - `should produce the same set of index calls on a second run over an unchanged tree` (run twice; assert the two recorded call sets are equal and no path appears twice within a single run)
  - `should propagate an indexer failure, still release the mirror tree, and not invoke the seeder` (indexer raises; assert exception surfaces, `tree` `finally` ran, and `seeder.seed` was never called — a failed walk must not publish a "synced" state)

### Phase 5: store-level end-to-end (integration)

- [x] **Task 11: two backfills leave exactly one copy of each artifact's chunks**
  Files: `tests/knowledge/test_knowledge_sync.py`
  Test cases:
  - `should leave exactly one copy of each artifact chunks after two consecutive backfills` (real `ArtifactIndexer`, stub `Embedder` returning fixed-dim vectors, in-memory `KnowledgeStore` keyed `(repo, path)`; run backfill twice over an unchanged tree; assert each `(repo, path)` holds exactly one set of chunks — the end-to-end "the store never accumulates history" that the call-level idempotency case cannot see)
