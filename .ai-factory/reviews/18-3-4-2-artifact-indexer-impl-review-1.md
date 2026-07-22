# Code Review: 3.4.2 — Artifact indexer (impl)

**Scope reviewed:** `src/knowledge/source_strategy.py`, `src/knowledge/chunker.py`, `src/knowledge/indexer.py` (all changes in `git diff HEAD`). Cross-checked against `store.py`, `llm/embedder.py`, `github/mirror.py`, the red tests (`tests/knowledge/test_source_strategy.py`, `tests/knowledge/test_chunker.py`), and specs 07/43.

## Summary

The implementation greens both red-test files and the `ArtifactIndexer` wiring is clean: constructor DI of the three abstractions, no concrete construction, `zip(..., strict=True)` defends the chunk↔embedding alignment, and the empty-chunk path still upserts (clearing stale rows) as the plan requires. Selection logic (`source_strategy.py`) is correct for every parametrized path. No crashes, race conditions, type mismatches, or missing migrations found.

One correctness finding on the chunker, below.

## Findings

### 1. `chunk_markdown` treats `#` comment lines inside fenced code blocks as headings — corrupts chunk boundaries on real selected artifacts (medium)

`src/knowledge/chunker.py:5` — `_HEADING_RE = r"^(#{1,6})[ \t]+\S.*$"` is applied to the raw document with no awareness of fenced code blocks (```` ``` ````). Any code-comment line that begins with `#` at column 0 is matched as a Markdown heading.

This is not hypothetical — it fires on the primary selected artifact, `CLAUDE.md`, which the default profile selects. Inside its ```` ```bash ```` first-time-setup fence:

```
33:# 1. Install pgvector for the SAME Postgres major your server runs...
34:#    multi-major box, build from source against that server's pg_config:
35:#      git clone https://github.com/pgvector/pgvector && cd pgvector
36:#      make install PG_CONFIG=/usr/local/opt/postgresql@17/bin/pg_config
37:# 2. Create Herald's role, database, and extension:
```

Each of these matches as a **level-1** heading. The real document headings are all `##`/`###` (level 2+). So in `chunk_markdown`:

- `_split_at_min_level_headings(text, skip_first=False)` computes `min_level = 1` from the code comments.
- The split points become lines 33–37, **not** the real `##` sections.
- The leading chunk runs from the top through line 32, cutting the ```` ```bash ```` block in half (opening fence + first commands in one chunk, the rest of the block in others).
- The final `# 2.` "section" runs to end-of-file, swallowing `## Architecture`, `## Patterns to follow`, `## Verification`, `## Logging`, and `## Documentation` into a **single** chunk keyed off a shell-comment line.

**Failure scenario:** `index(repo, "CLAUDE.md", tree)` stores chunks whose boundaries fall on shell-comment lines instead of `##` sections, one chunk merges five unrelated real sections, and a fenced code block is split across chunks. No exception is raised and no content is lost, so it passes silently — but retrieval returns "plausible but wrong" units. This is exactly the hazard spec 43/07 names ("a section split mid-thought reads as a plausible but wrong retrieval unit," "poisons retrieval with no exception raised"). The red tests don't cover fenced content, so they stay green while the contract is violated on shipped artifacts.

**Note on scope/severity:** content is preserved and nothing crashes, so this is a quality/correctness degradation rather than a runtime break. The fix is to skip lines inside ```` ``` ````/`~~~` fenced regions when detecting headings (track fence open/close state, or mask fenced spans before running `_HEADING_RE`). Given the chunker's whole contract is "split on *Markdown* headings" and a `#` inside a code fence is not one, I consider this in-scope for the task even though the red tests don't exercise it. Verdict: CONFIRMED.

## Non-issues considered

- **Missing-file read** (`indexer.py:38`, `(tree / path).read_text`): raises `FileNotFoundError` if a selected path is absent in the tree. Fail-loud is acceptable — the caller (3.6) drives `index` vs `remove` and holds the worktree; not a defect.
- **Empty-chunk upsert:** `chunk_markdown("") → []`, `embed([]) → []` (guard at `embedder.py:25`), `zip(strict=True)` over two empty lists → `[]`, and `PgVectorStore.upsert` still runs its `DELETE` inside the txn. Stale chunks are cleared. Correct.
- **`Chunk` defaults:** leaving `repo`/`path`/`chunk_index` at `None` is fine — `upsert` assigns `repo`/`path` from args and `chunk_index` from `enumerate`.
- **`_split_by_paragraphs` can emit a chunk > `MAX_CHUNK_CHARS`** for a single oversized blank-line-free paragraph: intentional per its docstring ("kept intact rather than cut mid-sentence") and consistent with the "never mid-sentence" guard.
- **Selection logic:** every `SELECTED_PATHS`/`NOT_SELECTED_PATHS` case in the red test resolves correctly; `str.startswith(tuple)` usage is valid.
