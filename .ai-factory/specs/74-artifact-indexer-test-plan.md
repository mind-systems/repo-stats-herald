# ArtifactIndexer — Test Plan

**Date:** 2026-07-29
**Source:** roadmap-test-coverage agent

## Source Overview

`ArtifactIndexer` (`src/knowledge/indexer.py`) drives the read → chunk → embed → upsert path for exactly one source file. `index(repo, path, tree)` returns early when `SourceStrategy.selects(path)` is false, otherwise reads `tree / path` as UTF-8 (skipping on `UnicodeDecodeError`), runs `chunk_markdown`, batches every chunk through one `Embedder.embed` call, zips chunks to embeddings with `strict=True` into `Chunk(content, embedding)`, and calls `KnowledgeStore.upsert(repo, path, items)`. `remove(repo, path)` is an unconditional delegation to `KnowledgeStore.delete`. It owns orchestration only — selection, chunk boundaries and store semantics all live in collaborators.

## Instantiation

`ArtifactIndexer(strategy, embedder, store)` — three constructor-injected collaborators, no concrete client built internally. Everything is fakeable in-process; no Postgres, no network, no `RepoMirror`.

- **`FakeSourceStrategy(SourceStrategy)`** — subclass the ABC (only `selects` is abstract; `roadmap_paths` has a default). Give it a configurable selected-path set (or predicate) plus `self.calls: list[str]` so tests can assert the indexer actually consulted it. For one end-to-end pass, use the real `AiFactorySourceStrategy` with the exemplar paths from spec 07.
- **`FakeEmbedder(Embedder)`** — `self.calls: list[list[str]]`, returns **position-distinct** vectors (e.g. `[[float(i)] for i, _ in enumerate(texts)]`), plus knobs for (a) returning a deliberately mismatched vector count and (b) raising. Do **not** copy `tests/reasoning/conftest.py`'s `FakeEmbedder` — its single `SENTINEL_VECTOR` for every text makes reordering bugs invisible. Must tolerate `embed([])`.
- **`FakeKnowledgeStore(KnowledgeStore)`** — implement all three abstract methods; record `self.upserts: list[tuple[str, str, list[Chunk]]]` and `self.deletes: list[tuple[str, str]]`; `query` can return `[]`. Optional `error` knob for the propagation case.
- **Tree** — a real `tmp_path`; write real files (`(tmp_path / ".ai-factory" / "specs").mkdir(parents=True)`), including a real binary file via `write_bytes` for the UTF-8 case. `tree` must stay a `Path` (the code does `tree / path`).
- **`chunk_markdown`** — use the real function (pure, fast, already pinned). Only monkeypatch `src.knowledge.indexer.chunk_markdown` if a test needs an exact synthetic chunk count; prefer a fixture doc with N clearly distinct `##` sections.
- `asyncio_mode = "auto"` in `pyproject.toml` — plain `async def test_*`, no marker. Suggested file `tests/knowledge/test_artifact_indexer.py`; do **not** request the `pg_pool` / `store` fixtures from `tests/knowledge/conftest.py` (they open a real Postgres pool).

## Existing Coverage

Layers below this one are already pinned and must not be re-tested here:

- `tests/knowledge/test_source_strategy.py` — the full selected / not-selected path matrix for `AiFactorySourceStrategy`.
- `tests/knowledge/test_chunker.py` — heading-section chunking and oversized-section splitting.
- `tests/knowledge/test_knowledge_store_contract.py` — `upsert` atomic replacement + `chunk_index` renumbering, `delete` scoping, `query` cosine ordering (Postgres-backed).

Nothing currently exercises `ArtifactIndexer` itself, and nothing exercises its caller `KnowledgeSync` (`src/knowledge/sync.py`) — the sync layer is out of scope for this plan.

## Test Cases

### `index` — the selection gate (central silent-failure hazard)

1. **should upsert the file's chunks when the strategy selects the path** — `index`. Baseline positive control for the gate; write a small multi-section doc at `CLAUDE.md` in the tmp tree and assert one `upsert` recorded for `(repo, "CLAUDE.md")`.
2. **should perform no read, no embed and no upsert when the strategy does not select the path** — `index`. Non-obvious setup: the non-selected file (`.ai-factory/plans/17-x.md`) **must actually exist on disk with real content**, so the no-op is provably caused by the gate rather than by a failed read. Assert `embedder.calls == []` *and* `store.upserts == []` — asserting only the store would let an inverted branch that still embeds (and burns tokens) pass.
3. **should leave the store completely untouched — no delete either — for a non-selected path** — `index`. Guards against a "skip" implemented as "upsert nothing", which would wipe previously indexed chunks: assert `store.deletes == []` alongside `store.upserts == []`.
4. **should route the decision through the injected strategy rather than any built-in path knowledge** — `index`. Inject a strategy that selects *only* `src/main.py` and rejects `CLAUDE.md`; assert `src/main.py` is indexed and `CLAUDE.md` is skipped. This is the inversion detector that a fixed real-strategy path list cannot provide, and it also pins that `selects` was called with the repo-relative `path` (not the joined absolute path).
5. **should index governing artifacts and skip orchestrator noise across spec 07's exemplars** — `index`, parametrized with the real `AiFactorySourceStrategy`. Selected: `CLAUDE.md`, `.ai-factory/ARCHITECTURE.md`, `.ai-factory/specs/03-x.md`. Not selected: `.ai-factory/plan-reviews/01-x.md`, `.ai-factory/handoffs/02-x.md`, `src/main.py`. Assert upsert-count 1 vs 0 only — no assertions about *why* a path is selected.

### `index` — chunk → embed → upsert wiring

6. **should send every chunk to the embedder in document order in a single batch call** — `index`. Assert `len(embedder.calls) == 1` and `embedder.calls[0] == chunk_markdown(text)`; a per-chunk loop or a reordered batch both fail here.
7. **should pair each chunk's content with the embedding returned at the same position** — `index`. With position-distinct fake vectors, assert `[(c.content, c.embedding) for c in items]` matches the expected zip; catches an off-by-one or reversed pairing that would leave every chunk retrievable under the wrong vector with no crash.
8. **should preserve chunk order in the upserted item list** — `index`. Assert `[c.content for c in items] == chunk_markdown(text)`. Order *is* `chunk_index`: `PgVectorStore.upsert` derives the index from list position, so this is the only place ordering can be pinned (see Gotchas).
9. **should upsert under the exact `(repo, path)` it was handed** — `index`. Assert the recorded key is the verbatim `repo` string and the repo-relative posix `path`, not an absolute or tree-joined path.
10. **should read the file from the tree it was given** — `index`. Create two tmp trees holding the same `path` with different content; index from the second and assert the upserted chunk content came from that tree. Pins that no ambient cwd / mirror lookup sneaks in.
11. **should upsert the newly read content when the same path is re-indexed** — `index`. Rewrite the file between two `index` calls and assert the second recorded upsert carries the new content. Idempotent replacement itself is the store's contract — assert only that a second full upsert is issued.

### `index` — degenerate and error paths

12. **should still call upsert with an empty item list when the file is empty or whitespace-only** — `index`. `chunk_markdown("")` returns `[]`, so the indexer embeds `[]` and upserts `[]` — the mechanism by which an emptied source gets cleared. Pin `store.upserts == [(repo, path, [])]`; a future "skip when no chunks" short-circuit would silently strand stale chunks for that path.
13. **should skip without touching the store when the file is not valid UTF-8** — `index`. Setup: `write_bytes(b"\xff\xfe\x00\x01binary")` at a *selected* path. Assert no upsert, no delete, and no exception — this branch is what keeps `KnowledgeSync.backfill`'s `rglob` over binaries from exploding.
14. **should propagate `FileNotFoundError` when a selected path is absent from the tree** — `index`. Only `UnicodeDecodeError` is caught; a missing selected file must fail loudly, not vanish. Assert the raise *and* that the store recorded nothing.
15. **should return quietly when a non-selected path is absent from the tree** — `index`. The gate precedes the read, so a missing non-selected path is a plain no-op; no `FileNotFoundError`. Pins gate-before-read ordering, which case 14 alone does not.
16. **should raise and upsert nothing when the embedder returns a different number of vectors than chunks** — `index`. Fake returns `len(chunks) - 1` vectors; `zip(..., strict=True)` raises `ValueError` before the store call. Assert `store.upserts == []` so no partial/truncated write is observable.
17. **should propagate an embedder failure without upserting** — `index`. Fake `embed` raises `RuntimeError`; assert propagation and `store.upserts == []`.
18. **should propagate a store failure to the caller** — `index`. Fake `upsert` raises; the indexer has no swallow, and `KnowledgeSync` relies on that to surface a broken backfill.

### `remove`

19. **should delete exactly the given `(repo, path)` from the store** — `remove`. Assert `store.deletes == [(repo, path)]`.
20. **should delete unconditionally without consulting the strategy** — `remove`. Call with a non-selected path (e.g. `.ai-factory/plans/17-x.md`) and assert the delete still happened and `strategy.calls == []`. `KnowledgeSync.on_push` already gates removals via `selects`; a second gate here would strand chunks for a path that changed category.
21. **should not embed or upsert on remove** — `remove`. Assert `embedder.calls == []` and `store.upserts == []`.

## Gotchas

- **Batch-embed ordering.** There is exactly one `embed` call per file, and content↔vector pairing is purely positional. A fake that returns the same vector for every text (as `tests/reasoning/conftest.py` does) makes reversal, rotation and off-by-one bugs untestable — return position-distinct vectors.
- **`chunk_index` is never set by the indexer.** It builds `Chunk(content=..., embedding=...)` and leaves `chunk_index=None`; `PgVectorStore.upsert` assigns the index from `enumerate(items)`. Asserting `item.chunk_index == i` would assert `None` and pass vacuously — assert **list order** into `upsert` instead.
- **Tree `Path` handling.** `tree` must be a `Path` (`tree / path` fails for `str / str`), `path` must be repo-relative posix, and nested paths need `mkdir(parents=True)` in the tmp tree. Note that an absolute `path` argument would make `tree / path` silently escape the tree — case 9 is the closest guard.
- **Repo-key form.** `repo` is an opaque pass-through key. In production it is the bare repository name (`payload["repository"]["name"]` → `PushEvent.repo` → `KnowledgeSync`), while the store contract tests use `"org/repo"` strings. Assert identity of whatever was passed in; do not encode or assert a naming format.
- **Mismatched embedder count.** `zip(chunks, embeddings, strict=True)` turns a short/long embedder response into a `ValueError` that escapes `index` with nothing written. That loud failure is the desired behavior — pin it so a later "drop `strict=True`" refactor (which would silently truncate a document's tail out of retrieval) is caught.
- **Empty file.** `chunk_markdown` filters blank chunks, so an empty or whitespace-only file yields `[]`; the indexer still calls `embed([])` and `upsert(repo, path, [])`. Assert the indexer's call shape only — the resulting row deletion belongs to the store contract test.
- **Other read errors are not caught.** `IsADirectoryError` / `PermissionError` from `read_text` propagate; `KnowledgeSync` already filters non-files with `is_file()`, so no test is needed, but do not "improve" the except clause without a spec change.
- **Logging is not behavior.** The debug/info lines on the skip and success paths carry no observable contract — do not assert on `caplog`; assert on collaborator calls.
- **Test isolation.** `tests/knowledge/conftest.py` provides Postgres-backed `pg_pool` / `store` fixtures; the new unit tests must not request them (the pure `make_chunk` fixture is safe) so the file stays DB-free.
