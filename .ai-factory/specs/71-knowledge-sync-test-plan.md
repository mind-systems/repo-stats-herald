# KnowledgeSync — Test Plan

**Date:** 2026-07-29
**Source:** roadmap-test-coverage agent

## Source Overview

`KnowledgeSync` (`src/knowledge/sync.py`) is the only writer that keeps a served repo's *semantic* memory equal to "what the project is now." `backfill(repo, org_id)` walks an isolated mirror tree at the repo's canonical ref and hands every file to `ArtifactIndexer.index`; `on_push(push)` re-indexes only the paths a push touched, and only when the push landed on that repo's canonical ref. Semantic memory has no branch dimension, so the canonical-ref gate in `on_push` is the sole thing preventing a feature branch from overwriting the project's current answer — silently, with no crash.

## Instantiation

```python
KnowledgeSync(mirror, indexer, strategy, canonical_refs, seeder=None)
```

All five collaborators are constructor-injected; nothing is built internally, so no patching of module globals is needed. Note that `_canonical_ref` delegates to the module-level `resolve_canonical_ref` imported into `src.knowledge.sync` — a fake mirror only needs to satisfy the duck-typed surface it uses.

What to fake, and how:

- **`mirror` — fake `RepoMirror`.** Only three members are touched: `ensure(repo, org_id)`, `default_branch(repo)`, and `tree(repo, org_id, ref)` as a `@contextmanager` yielding a `Path`. Model it on the existing `_FakeMirror` in `tests/graph/test_coordination_seeder.py`: build a `TemporaryDirectory`, materialize a dict of `{relative_path: content}` into it, yield the path. Extend it to record every `ensure` and `tree` call as `(repo, org_id, ref)` tuples — the gate tests assert on `tree` calls *not* happening. Pass with `# type: ignore[arg-type]`, matching the seeder tests' convention. No git, no network.
- **`indexer` — fake `ArtifactIndexer`** with `async def index(repo, path, tree)` and `async def remove(repo, path)`, each appending to a list. Record `tree` too for the "tree is opened at `push.after`" case. A variant that raises on a chosen path covers the error path.
- **`strategy` — real `AiFactorySourceStrategy`** for realism, plus a tiny stub `SourceStrategy` whose `selects` records its arguments — needed to prove the strategy is *never consulted* on a non-canonical push.
- **`canonical_refs` — a plain dict.** `{}` exercises the default-branch fallback through the fake mirror; `{"repo": "release"}` exercises the override.
- **`seeder` — optional fake `CoordinationSeeder`** with `async def seed(repo, org_id)` recording calls; also test `None` explicitly.
- **Store**: not a collaborator of `KnowledgeSync` — it sits behind `ArtifactIndexer`. Only the one integration-flavored case below needs a real/in-memory `KnowledgeStore`, wired through a real `ArtifactIndexer` with a stub `Embedder` returning fixed-dim vectors.

`asyncio_mode = "auto"` is set in `pyproject.toml`, so `async def test_*` needs no marker. Suggested location: `tests/knowledge/test_knowledge_sync.py`. Do **not** reuse `tests/knowledge/conftest.py`'s `pg_pool`/`store` fixtures unless writing the integration case — they require a live Postgres.

## Existing Coverage

**None.** `grep -rn KnowledgeSync tests/` returns no hits. `src/ingestion/router.py` dispatches `knowledge_sync.on_push` as a background task, but `tests/ingestion/test_webhook_contract.py` builds `TestClient(app)` without running `lifespan`, so `app.state.knowledge_sync` is absent and that dispatch is never exercised. The canonical-ref gate is, today, completely untested.

## Test Cases

### `on_push` — the canonical-ref gate (highest priority)

1. **should perform no indexing, no removal, and open no mirror tree when the push branch is not the canonical ref** — `on_push`. Setup: `canonical_refs={"repo": "main"}`, push with `branch="feature/x"` whose commits add/modify/remove *curated* paths (`docs/a.md`, `.ai-factory/specs/1.md`, `ROADMAP.md`) so the only thing that could suppress work is the gate itself, not path selection. Assert `indexer.index` calls == `[]`, `indexer.remove` calls == `[]`, and the fake mirror recorded zero `tree` calls. This is the inversion detector.
2. **should not consult the source strategy at all when the push branch is not the canonical ref** — `on_push`. Setup: stub strategy recording `selects` arguments; the push removes a curated path. Assert `strategy.selects` was never called. Pins the spec's literal wording and stops a refactor that hoists path filtering above the gate.
3. **should not invoke the coordination seeder when the push branch is not the canonical ref** — `on_push`. Assert `seeder.seed` calls == `[]`. Seeding re-materializes graph edges from the branch's `CLAUDE.md`; it is downstream state that must stay behind the gate too.
4. **should still ensure the mirror before deciding, on a non-canonical push** — `on_push`. Assert `mirror.ensure` was called exactly once with `(push.repo, push.org_id)` even though nothing else ran. Documents the deliberate ordering: `ensure` must precede `default_branch`, which reads the bare clone's `HEAD`.
5. **should index changed paths when the push branch equals the canonical ref** — `on_push`. Same push as case 1 but `branch="main"`. The positive half of the gate — without it, case 1 passes trivially if `on_push` becomes a no-op.
6. **should gate on the resolved override rather than the mirror default branch when `canonical_refs` names the repo** — `on_push`. Setup: fake mirror `default_branch` returns `"main"`, `canonical_refs={"repo": "release"}`; run one push on `branch="release"` (expect indexing) and one on `branch="main"` (expect nothing). Proves the override wins in both directions.
7. **should gate on the mirror's default branch when `canonical_refs` has no entry for the repo** — `on_push`. Setup: `canonical_refs={}` (or an entry for a *different* repo, to catch a wrong-key lookup), fake `default_branch` returns `"trunk"`; push on `"trunk"` indexes, push on `"main"` does not.

### `on_push` — changed-path derivation

8. **should derive the changed set as the union of added, modified, and removed across every commit in the push** — `on_push`. Setup: three commits, each contributing a distinct path in a distinct bucket, plus one path repeated across two commits. Assert the recorded paths as a **set** (iteration order over `changed_paths` is nondeterministic — never assert a list order) and assert the duplicated path produced exactly one call.
9. **should index a path that exists in the tree at `push.after`, regardless of which bucket the commit listed it in** — `on_push`. Setup: a path listed under `removed` in an early commit but re-added later and present in the tree. Assert it is indexed, not removed. The code branches on tree existence, not on the bucket — correct last-writer-wins semantics.
10. **should delete a removed curated path from the store when it is absent from the tree** — `on_push`. Assert `indexer.remove(repo, "docs/gone.md")` was called and `index` was not. Pins the "removed paths are deleted — no orphan chunks" guard.
11. **should not call remove for a non-curated path that is absent from the tree** — `on_push`. Setup: commit removes `src/deleted.py`, real `AiFactorySourceStrategy`. Assert `remove` calls == `[]`.
12. **should open the tree but index nothing when the canonical push touches only non-curated code paths** — `on_push` with a real `ArtifactIndexer` (stub embedder + recording store). Note that `KnowledgeSync` itself *does* call `indexer.index` for these — filtering lives inside `ArtifactIndexer.index`. Assert at the store boundary, not at the `index` boundary, or the test pins the wrong layer.
13. **should treat a modified path that is missing from the tree as a removal when it is curated** — `on_push`. Setup: `modified=("docs/x.md",)` but the tree at `push.after` lacks it (force-push / rewritten history). Documents the fallthrough as intentional.
14. **should complete without indexing or removing anything when the canonical push carries no commits** — `on_push` with `commits=()`. Assert no index/remove calls, and that the seeder still ran (a zero-commit canonical push is still a canonical-ref state change).

### `on_push` — tree pinning and fan-out

15. **should open the mirror tree at `push.after` rather than at the canonical ref name** — `on_push`. Setup: fake mirror recording `tree` call args; push `branch="main"`, `after="deadbeef"`. Assert the recorded ref == `"deadbeef"`. A regression here would index whatever `main` currently points at, racing concurrent pushes; the log line says `ref=canonical` and could mislead a reader into "fixing" this.
16. **should pass the yielded tree path to the indexer for every indexed file** — `on_push`. Pins isolated-tree reads — a switch to a shared checkout would still make the other tests pass.
17. **should invoke the coordination seeder once after indexing on a canonical push** — `on_push`. Pair with an ordering assertion (seed recorded after the last `index`) via a shared call log.
18. **should complete normally when no seeder was injected** — `on_push` with `seeder=None`. The `None` default is real: `scripts/backfill.py` and any partially-configured composition root may omit it.
19. **should propagate an indexer failure and still release the mirror tree** — `on_push`. Assert the exception surfaces (the router's `_run_isolated` is what swallows it, not this class) and that the fake mirror's `tree` context manager ran its `finally`. Swallowing here would make a partial index look like a clean sync.

### `backfill`

20. **should index every non-`.git` file in the tree at the canonical ref** — `backfill`. Assert the recorded index paths as a set equal all files — `backfill` intentionally does *not* pre-filter; selection is the indexer's job. Anchoring the expectation to "curated only" here would mis-pin the layering.
21. **should pass repo-relative POSIX paths to the indexer, not absolute paths** — `backfill`. Setup: nested file `docs/nested/deep/a.md`. Absolute or OS-separator paths would silently break `strategy.selects`' prefix matching and the store's `(repo, path)` key — no crash, just an empty store.
22. **should skip everything under a `.git` directory** — `backfill`. The filter is `".git" in path.parts`, an exact path-component match — a sibling case with `docs/.gitignore` and `.gitkeep` should assert those *are* passed through, guarding against a `startswith(".git")` regression.
23. **should skip directories and index only files** — `backfill`. `rglob("*")` yields directories too.
24. **should open the tree at the canonical ref resolved from `canonical_refs` when an override exists** — `backfill`. Assert the recorded `tree` ref == `"release"` and that `default_branch` was never consulted.
25. **should open the tree at the mirror's default branch when `canonical_refs` has no entry** — `backfill`.
26. **should ensure the mirror before resolving the canonical ref** — `backfill`. Setup: fake mirror whose `default_branch` raises unless `ensure` has already run (mirrors the real class, which shells out to `git symbolic-ref` inside the bare clone). Locks the ordering dependency that a pure call-count assertion would miss.
27. **should invoke the coordination seeder once after the walk completes** — `backfill`.
28. **should complete without a seeder when none was injected** — `backfill` with `seeder=None`.
29. **should produce the same set of index calls on a second run over an unchanged tree** — `backfill`. Run twice; assert the two recorded call sets are equal and that no path appears twice within a single run.
30. **should leave exactly one copy of each artifact's chunks after two consecutive backfills** — `backfill`, integration variant with a real `ArtifactIndexer`, a stub `Embedder`, and an in-memory `KnowledgeStore` keyed `(repo, path)`. This is the end-to-end statement of "the store never accumulates history"; the call-level case 29 cannot see duplicate rows.
31. **should complete without error and index nothing when the tree is empty** — `backfill`.
32. **should propagate an indexer failure and still release the mirror tree** — `backfill`, mirroring case 19. Also assert the seeder was *not* invoked, since a failed walk must not publish a "synced" graph state.

## Gotchas

- **Async fan-out.** Both methods `await` the indexer inside a synchronous `with self._mirror.tree(...)` block, so the tree context manager must be a *sync* `@contextmanager` in the fake — an `@asynccontextmanager` fake fails with an unrelated `AttributeError` and obscures the real assertion. Fake `index`/`remove`/`seed` must be `async def`; a plain `Mock` returns a non-awaitable and blows up at the `await`.
- **Changed-path derivation is a `set`.** Iteration order is nondeterministic across runs. Every assertion about `on_push` call sequences must compare sets, or sort, or use per-path membership. Only *relative* ordering between phases (all indexing before `seed`) is guaranteed.
- **Deletes vs upserts branch on tree existence, not on the commit bucket.** Fixtures must control the tree contents independently of the commit buckets, or the tests pin an accidental correlation.
- **The delete branch is strategy-guarded; the index branch is not.** `KnowledgeSync` calls `indexer.index` for every existing changed path and lets `ArtifactIndexer.index` drop non-selected ones, but calls `indexer.remove` only when `strategy.selects(path)`. Assertions about "only curated artifacts are stored" belong at the *store* boundary; assertions about "no pointless deletes" belong at the *indexer* boundary.
- **Default-branch fallback runs through `resolve_canonical_ref`**, imported into `src.knowledge.sync`. `canonical_refs.get(repo)` returning `None` is the only fallback trigger. Prefer a fake `default_branch` that returns something *other* than `"main"` (e.g. `"trunk"`) so a hardcoded-`"main"` regression cannot pass.
- **`ensure` precedes the gate on purpose.** Assert the gate suppresses *tree opening and all semantic writes* — not that `on_push` returns before touching the mirror at all.
- **`push.after` vs the canonical ref name.** `on_push` opens the tree at the immutable `push.after` SHA while logging `ref=canonical`. A fake mirror that ignores its `ref` argument lets a regression to `tree(..., canonical)` pass unnoticed.
- **Idempotency has two layers.** At the `KnowledgeSync` layer, re-running produces the same call set (case 29). The no-duplicate-rows guarantee lives in the store's `(repo, path, chunk_index)` key and is only observable with a real indexer plus a store double (case 30).
- **`.git` filtering is component-exact.** Include a positive case for dotfiles so a `startswith` "simplification" is caught.
- **`seeder=None` is a live configuration**, not a test-only convenience. Both methods need an explicit `None` case.
