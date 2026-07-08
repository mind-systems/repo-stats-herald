# 3.4.2 — Artifact indexer (impl)

**Phase:** 3 — Repo mirror & semantic memory. Depends on 3.4.1 (the `SourceStrategy`/`chunk_markdown` contract and its red tests), 3.1 (the mirror, for a tree to read from), 3.2 (embed), 3.3 (the store). Second half of the indexer milestone — wires 3.4.1's pure logic into a store-backed indexer.

## Current state

3.4.1 defines `SourceStrategy` (the default ai-factory profile) and `chunk_markdown`, both pinned with red tests, but pure — nothing yet reads a real file from a mirror tree or writes to the store. 3.1 keeps an isolated mirror tree per operation, 3.2 embeds text, 3.3 stores/queries vectors — nothing yet drives read → chunk → embed → upsert for one source.

## Change

Add the indexer that reads a source from an isolated mirror tree into the store, using 3.4.1's selection and chunking.

- `src/knowledge/indexer.py` — `ArtifactIndexer`:
  - `index(repo: str, path: str, tree: Path)` — if `SourceStrategy.selects(path)`: read the file from the **isolated mirror tree at the target ref** (3.1's `RepoMirror.tree(...)`, the caller holds it open for the duration) → `chunk_markdown` → `Embedder.embed` → `KnowledgeStore.upsert(repo, path, chunks+embeddings)`; otherwise a no-op.
  - `remove(repo: str, path: str)` — `KnowledgeStore.delete(repo, path)`.
- Assembled at the composition root from the injected strategy/embedder/store.

## Files & types

- new `src/knowledge/indexer.py` (`ArtifactIndexer`)

## Guards

- Reads the source from an isolated mirror tree (3.1) passed in by the caller — no network fetch here, and no direct dependency on the mirror's internals beyond the tree path it's handed.
- `index` on a path the strategy does not select is a no-op (skipped, not stored) — reuses 3.4.1's `selects`, does not re-implement it.
- Re-indexing replaces a source's chunks (via 3.3's per-`(repo, path)` upsert) — idempotent.
- Chunking reuses 3.4.1's `chunk_markdown` unchanged.

## Verification

- `index(repo, "CLAUDE.md", tree)` reads the tree's `CLAUDE.md` and populates queryable chunks matching its sections.
- `index(repo, ".ai-factory/ARCHITECTURE.md", tree)` and `index(repo, ".ai-factory/specs/03-x.md", tree)` are selected and populate chunks — the pruned/shipped knowledge and the feature specs are captured.
- `index(repo, ".ai-factory/plan-reviews/01-x.md", tree)`, `index(repo, ".ai-factory/handoffs/02-x.md", tree)`, and `index(repo, "src/main.py", tree)` are no-ops (not selected by the default profile).
- `remove(repo, "CLAUDE.md")` clears that file's chunks.
