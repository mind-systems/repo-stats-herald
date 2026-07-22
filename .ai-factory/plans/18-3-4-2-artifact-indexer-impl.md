# Plan: 3.4.2 — Artifact indexer (impl)

## Context
Fill in the pure selection/chunking bodies stubbed by 3.4.1 and add `ArtifactIndexer`, which reads a selected source from an isolated mirror tree, chunks it, embeds it, and upserts it into the knowledge store — greening 3.4.1's red tests and completing the read → chunk → embed → upsert path for one source.

## Settings
- Testing: no
- Logging: minimal
- Docs: no

## Tasks

### Phase 1: Green the pure 3.4.1 logic

- [x] **Task 1: Implement `AiFactorySourceStrategy.selects`**
  Files: `src/knowledge/source_strategy.py`
  Replace the `raise NotImplementedError` in `selects(self, path: str) -> bool` with the default ai-factory profile. Selected (return `True`):
  - `CLAUDE.md` and `AGENTS.md` **at the repo root only** (bare filename, no directory prefix);
  - `ARCHITECTURE.md` and `ROADMAP.md` whether at the root **or** directly under `.ai-factory/` (i.e. basename is `ARCHITECTURE.md`/`ROADMAP.md` and the path is either the bare filename or `.ai-factory/<name>`);
  - anything under `.ai-factory/specs/` (prefix `.ai-factory/specs/`);
  - anything under `docs/` (prefix `docs/`).
  Everything else returns `False` — in particular `.ai-factory/plans/**`, `.ai-factory/plan-reviews/**`, `.ai-factory/reviews/**`, `.ai-factory/notes/**`, `.ai-factory/handoffs/**`, and code paths (`src/**`). Match against the repo-relative path as given (forward slashes); do not read the filesystem — this stays pure. Keep the docstring's contract accurate. Verify against `tests/knowledge/test_source_strategy.py` (both the `SELECTED_PATHS` and `NOT_SELECTED_PATHS` parametrizations must pass).

- [x] **Task 2: Implement `chunk_markdown`**
  Files: `src/knowledge/chunker.py`
  Replace the `raise NotImplementedError` in `chunk_markdown(text: str) -> list[str]`. Split the document on Markdown headings into whole sections — a heading line plus its body up to (but not including) the next heading of the same-or-shallower level become one chunk, so a retrieved chunk keeps its point. Text before the first heading, if any non-blank, is its own leading chunk. Drop blank/whitespace-only chunks.
  For an oversized section (`len(section) > MAX_CHUNK_CHARS`): split further on the section's sub-headings first, then, if a piece is still oversized, on paragraph (blank-line) boundaries — **never mid-sentence**. Each emitted piece must satisfy the test's boundary rule (`_ends_at_boundary`): its last non-blank line either starts with `#` or the chunk ends with `.`/`!`/`?`. Preserve heading + body text within each chunk.
  Verify against `tests/knowledge/test_chunker.py` — the multi-section split (one chunk per `##` section, heading+body kept together) and the oversized-section split (more than one chunk, each ending at a heading or sentence boundary).

### Phase 2: The store-backed indexer

- [x] **Task 3: Add `ArtifactIndexer`** (depends on Task 1, Task 2)
  Files: `src/knowledge/indexer.py` (new)
  Add class `ArtifactIndexer` with constructor DI of the three abstractions — `SourceStrategy`, `Embedder` (from `src/llm/embedder.py`), and `KnowledgeStore` (from `src/knowledge/store.py`) — stored on private attributes; the indexer never constructs a concrete client (composition-root wiring, per ARCHITECTURE.md). Import `Path` from `pathlib` and `Chunk` from `src.knowledge.store`.
  - `async def index(self, repo: str, path: str, tree: Path) -> None`:
    - if `not self._strategy.selects(path)`: return immediately (no read, no store write) — reuse `selects`, do not re-implement selection here;
    - otherwise read the file at `tree / path` (text, UTF-8) — `tree` is the isolated mirror worktree the caller (3.1's `RepoMirror.tree(...)` context manager) holds open for the duration; the indexer only ever touches this handed-in path, never the mirror's internals and never the network;
    - `chunks = chunk_markdown(text)`; call `self._embedder.embed(chunks)` to get one vector per chunk (order-aligned); zip them into `Chunk(content=..., embedding=...)` value objects (repo/path/chunk_index are assigned by the store on upsert, leave them at their defaults);
    - `await self._store.upsert(repo, path, items)` — 3.3's per-`(repo, path)` upsert replaces the source's prior chunks, so re-indexing is idempotent. An empty chunk list yields an empty `items` and a clean upsert (clears any stale chunks) — do not special-case it away in a manner that skips the clearing.
  - `async def remove(self, repo: str, path: str) -> None`: `await self._store.delete(repo, path)`.
  Log at debug/info via the `logging` module (module logger, no `print`): one line noting select-skip vs. indexed-with-N-chunks. Keep it minimal.
  This class is assembled at the composition root from the injected strategy/embedder/store (no wiring change ships in this task — 3.6 drives it).
