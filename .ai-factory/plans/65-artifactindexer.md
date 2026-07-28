# Test Plan: ArtifactIndexer

## Context
`ArtifactIndexer` (`src/knowledge/indexer.py`) owns the read → chunk → embed → upsert path for one source file: it gates on `SourceStrategy.selects`, batches chunks through one `Embedder.embed`, zips content↔vector positionally into `Chunk`, and upserts under `(repo, path)`; `remove` delegates unconditionally to `KnowledgeStore.delete`. This suite pins only that orchestration — selection rules, chunk boundaries and store semantics are already pinned by their own suites and must not be re-tested.

## Settings
- Testing: yes
- Logging: minimal
- Docs: no

## Test Command
`uv run pytest tests/knowledge/test_artifact_indexer.py`

## Target Spec File
`tests/knowledge/test_artifact_indexer.py`

## Fixtures & Fakes (build inside the new file — do NOT request `pg_pool` / `store` from `tests/knowledge/conftest.py`; they open a real Postgres pool)

- **`FakeSourceStrategy(SourceStrategy)`** — implement only `selects` (`roadmap_paths` has an ABC default). Configurable selected-path set/predicate; record `self.calls: list[str]` so tests can assert the indexer consulted it with the repo-relative `path`.
- **`FakeEmbedder(Embedder)`** — `self.calls: list[list[str]]`; return **position-distinct** vectors, e.g. `[[float(i)] for i, _ in enumerate(texts)]`. Knobs: (a) return a deliberately mismatched vector count, (b) raise. Must tolerate `embed([])`. Do NOT reuse `tests/reasoning/conftest.py`'s single-`SENTINEL_VECTOR` fake — it hides reorder/off-by-one bugs.
- **`FakeKnowledgeStore(KnowledgeStore)`** — implement all three abstract methods; record `self.upserts: list[tuple[str, str, list[Chunk]]]` and `self.deletes: list[tuple[str, str]]`; `query` returns `[]`; optional `error` knob for the propagation case.
- **Tree** — a real `tmp_path` (`Path`); write real files (`(tmp_path / ".ai-factory" / "specs").mkdir(parents=True)`); write a real binary file via `write_bytes` for the UTF-8 case. `path` is repo-relative posix (`tree / path`).
- **`chunk_markdown`** — use the real function; prefer a fixture doc with N distinct `##` sections over monkeypatching `src.knowledge.indexer.chunk_markdown`.
- `asyncio_mode = "auto"` — plain `async def test_*`, no marker.

## Tasks

### Phase 1: `index` — the selection gate (the central silent-failure hazard)

- [x] **Task 1: `ArtifactIndexer.index` — selection gate routing**
  Files: `tests/knowledge/test_artifact_indexer.py`
  Test cases:
  - `should upsert the file's chunks when the strategy selects the path` — write a small multi-section doc at `CLAUDE.md`; assert exactly one `upsert` recorded for `(repo, "CLAUDE.md")`.
  - `should perform no read, no embed and no upsert when the strategy does not select the path` — the non-selected file (`.ai-factory/plans/17-x.md`) must exist on disk with real content; assert `embedder.calls == []` AND `store.upserts == []`.
  - `should leave the store completely untouched with no delete for a non-selected path` — assert `store.deletes == []` alongside `store.upserts == []` (guards against "skip" implemented as "upsert nothing").
  - `should route the decision through the injected strategy rather than built-in path knowledge` — inject a strategy that selects only `src/main.py` and rejects `CLAUDE.md`; assert `src/main.py` indexed, `CLAUDE.md` skipped, and `selects` was called with the repo-relative `path`.
  - `should index governing artifacts and skip orchestrator noise across spec 07 exemplars` — parametrized with the real `AiFactorySourceStrategy`. Selected → upsert-count 1: `CLAUDE.md`, `.ai-factory/ARCHITECTURE.md`, `.ai-factory/specs/03-x.md`. Not selected → upsert-count 0: `.ai-factory/plan-reviews/01-x.md`, `.ai-factory/handoffs/02-x.md`, `src/main.py`. Assert counts only, never *why* a path is selected.

### Phase 2: `index` — chunk → embed → upsert wiring

- [x] **Task 2: `ArtifactIndexer.index` — batching, ordering and pairing**
  Files: `tests/knowledge/test_artifact_indexer.py`
  Test cases:
  - `should send every chunk to the embedder in document order in a single batch call` — assert `len(embedder.calls) == 1` and `embedder.calls[0] == chunk_markdown(text)`.
  - `should pair each chunk's content with the embedding returned at the same position` — with position-distinct vectors, assert `[(c.content, c.embedding) for c in items]` matches the expected zip.
  - `should preserve chunk order in the upserted item list` — assert `[c.content for c in items] == chunk_markdown(text)` (order IS `chunk_index`; the indexer never sets `chunk_index`, so pin list order, not the field).

- [x] **Task 3: `ArtifactIndexer.index` — key, source tree and re-index**
  Files: `tests/knowledge/test_artifact_indexer.py`
  Test cases:
  - `should upsert under the exact (repo, path) it was handed` — assert the recorded key is the verbatim `repo` string and the repo-relative posix `path`, not an absolute/tree-joined path.
  - `should read the file from the tree it was given` — two tmp trees hold the same `path` with different content; index from the second and assert upserted content came from that tree.
  - `should upsert the newly read content when the same path is re-indexed` — rewrite the file between two `index` calls; assert the second recorded upsert carries the new content (assert only that a second full upsert is issued).

### Phase 3: `index` — degenerate and error paths

- [x] **Task 4: `ArtifactIndexer.index` — degenerate inputs**
  Files: `tests/knowledge/test_artifact_indexer.py`
  Test cases:
  - `should still call upsert with an empty item list when the file is empty or whitespace-only` — `chunk_markdown("")` is `[]`; pin `store.upserts == [(repo, path, [])]` (guards against a future "skip when no chunks" short-circuit that would strand stale chunks).
  - `should skip without touching the store when the file is not valid UTF-8` — `write_bytes(b"\xff\xfe\x00\x01binary")` at a selected path; assert no upsert, no delete, no exception.

- [x] **Task 5: `ArtifactIndexer.index` — read/embed/store error propagation**
  Files: `tests/knowledge/test_artifact_indexer.py`
  Test cases:
  - `should propagate FileNotFoundError when a selected path is absent from the tree` — assert the raise AND that the store recorded nothing (only `UnicodeDecodeError` is caught).
  - `should return quietly when a non-selected path is absent from the tree` — no `FileNotFoundError`; pins gate-before-read ordering.
  - `should raise and upsert nothing when the embedder returns a different number of vectors than chunks` — fake returns `len(chunks) - 1` vectors; `zip(..., strict=True)` raises `ValueError` before the store call; assert `store.upserts == []`.
  - `should propagate an embedder failure without upserting` — fake `embed` raises `RuntimeError`; assert propagation and `store.upserts == []`.
  - `should propagate a store failure to the caller` — fake `upsert` raises; assert the exception surfaces (no swallow).

### Phase 4: `remove`

- [x] **Task 6: `ArtifactIndexer.remove` — unconditional delegation**
  Files: `tests/knowledge/test_artifact_indexer.py`
  Test cases:
  - `should delete exactly the given (repo, path) from the store` — assert `store.deletes == [(repo, path)]`.
  - `should delete unconditionally without consulting the strategy` — call with a non-selected path (e.g. `.ai-factory/plans/17-x.md`); assert the delete happened and `strategy.calls == []`.
  - `should not embed or upsert on remove` — assert `embedder.calls == []` and `store.upserts == []`.

## Gotchas (from spec 74)
- **Batch-embed ordering** — exactly one `embed` call per file; pairing is purely positional. Position-distinct fake vectors are mandatory, or reversal/rotation/off-by-one bugs are untestable.
- **`chunk_index` is never set by the indexer** — it builds `Chunk(content=..., embedding=...)` leaving `chunk_index=None`. Asserting `item.chunk_index == i` passes vacuously against `None`; assert list order into `upsert`.
- **Tree `Path` handling** — `tree` must be a `Path`, `path` repo-relative posix; nested paths need `mkdir(parents=True)`. An absolute `path` would make `tree / path` escape the tree — Task 3's key case is the closest guard.
- **Repo-key form** — `repo` is an opaque pass-through (bare repo name in prod, `"org/repo"` in store tests). Assert identity of whatever was passed; do not encode or assert a naming format.
- **Empty file** — `chunk_markdown` filters blanks → `[]`; the indexer still calls `embed([])` and `upsert(repo, path, [])`. Assert the call shape only; the resulting row deletion belongs to the store contract test.
- **Logging is not behavior** — do not assert on `caplog`; assert on collaborator calls.
- **Test isolation** — must not request `pg_pool` / `store` from `tests/knowledge/conftest.py`; the pure `make_chunk` fixture is safe. Keep the file DB-free.
