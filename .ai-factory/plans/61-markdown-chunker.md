# Test Plan: Markdown chunker

## Context
`chunk_markdown` (`src/knowledge/chunker.py`) splits a Markdown document at its shallowest ATX heading level into whole sections, re-splitting oversized sections on sub-headings or paragraph boundaries. It is a pure function with 129 lines and only two tests today; the untested branches (preamble, no-heading, empty input, min-level rule, the exact size boundary, the paragraph-grouping fallback, and the whole code-fence machinery) degrade retrieval silently — plausible chunks, no exception. This plan pins the full contract, including behaviours that are arguably wrong (unclosed-fence merge, setext-blindness, over-limit single paragraph) as deliberate current behaviour.

## Settings
- Testing: yes
- Logging: minimal
- Docs: no

## Test Command
`uv run pytest tests/knowledge/test_chunker.py`

## Target Spec File
`tests/knowledge/test_chunker.py`

## Global Guards (apply to every task)
- Every size-sensitive fixture must be built against the imported `MAX_CHUNK_CHARS`, never a literal `2000`. Import the constant and pad/measure against it; assert the fixture's length before calling so it cannot drift.
- Do **not** assert a universal `len(chunk) <= MAX_CHUNK_CHARS`. A single over-limit paragraph is deliberately kept intact (verified: 2505 chars). The size limit yields to the "never mid-sentence" rule.
- Each test is `chunks = chunk_markdown(<literal string>)` plus assertions on the returned list. No instantiation, no mocks, no fixtures, no I/O.
- When pinning an arguably-wrong behaviour (unclosed fence, setext underline, parent-heading loss), add a code comment stating it is deliberate current behaviour, so a future change to it is an explicit decision — but keep comments free of any plan/roadmap/spec reference per project rules.
- Keep the two existing tests as regression anchors; extend rather than replace them where a task strengthens them.

## Tasks

### Phase 1: Section boundary detection (the core contract)

- [x] **Task 1: `chunk_markdown` — heading-section splitting**
  Files: `tests/knowledge/test_chunker.py`
  Test cases:
  - `should return one chunk per top-level heading section when the document has several same-level headings` — regression anchor; keep existing test 1.
  - `should keep the heading line and its body together in a single chunk when the section is under the limit` — assert on chunk text: `chunks[0].startswith("## Section One")`.
  - `should treat text before the first heading as its own leading chunk when a preamble precedes the first heading` — the `starts[0] > 0` branch.
  - `should return the whole document as one chunk when it contains no headings and fits the limit` — the `sections is None` → `[text]` branch.

- [x] **Task 2: `chunk_markdown` — shallowest-level (min-level) split rule**
  Files: `tests/knowledge/test_chunker.py`
  Test cases:
  - `should emit exactly one chunk when a single # heading is followed by several ## sub-headings totalling under the limit` — min-level is 1, one split start at index 0; the `##` headings do NOT start new chunks. The most surprising rule in the module; pin it.
  - `should split at ### level when the document's shallowest heading is ###` — confirms the split level is relative to the shallowest present, not absolute.
  - `should keep a deeper heading inside its parent chunk when a shallower sibling follows it` — e.g. `## A / ### A1 / ## B` → 2 chunks, `### A1` lives in chunk 0.

- [x] **Task 3: `_HEADING_RE` — what counts as an ATX heading**
  Files: `tests/knowledge/test_chunker.py`
  Test cases:
  - `should not treat a # with no space after it as a heading` — `#hashtag` and a bare `#` line are body text (`#{1,6}[ \t]+\S`).
  - `should not treat a run of 7 or more # as a heading` — `#######` exceeds the `{1,6}` bound.
  - `should not treat a heading marker followed only by whitespace as a heading` — `#{1,6}[ \t]+\S` requires a non-space char after the run.
  - `should not treat a setext (=== / ---) underline as a heading` — implementation is ATX-only; verified: returns a single chunk. Pin as a known limitation.

### Phase 2: Empty and degenerate input

- [x] **Task 4: `chunk_markdown` — empty, whitespace and blank-piece handling**
  Files: `tests/knowledge/test_chunker.py`
  Test cases:
  - `should return an empty list when the input is the empty string` — the `text.strip()` guard; verified `[]`.
  - `should return an empty list when the input is only whitespace and newlines` — verified `"   \n\n  "` → `[]`.
  - `should keep a heading with an empty body as its own chunk` — `"## A\n## B\n"` → verified `["## A\n", "## B\n"]`; the final `if chunk.strip()` filter must not eat heading-only sections.
  - `should drop a whitespace-only trailing piece rather than emit a blank chunk` — the terminal list comprehension / `piece.strip()` filter.

### Phase 3: Size threshold (`MAX_CHUNK_CHARS`)

- [x] **Task 5: `_ensure_size` — the exact size boundary**
  Files: `tests/knowledge/test_chunker.py`
  Test cases:
  - `should return the section as a single chunk when it is exactly MAX_CHUNK_CHARS long` — the `<=` branch. Build to exact length against the imported constant and assert `len(section) == MAX_CHUNK_CHARS` before the call.
  - `should split a section that is one character over MAX_CHUNK_CHARS when it has splittable structure` — pair with the exact-length case so a `<` vs `<=` flip fails one of them.

- [x] **Task 6: `_ensure_size` — oversized section split on sub-headings**
  Files: `tests/knowledge/test_chunker.py`
  Test cases:
  - `should split an oversized section on its nested sub-headings` — strengthen existing test 2 to assert which pieces come out, not merely `len > 1`.
  - `should keep the parent heading only on the leading piece when an oversized section is split on sub-headings` — verified: `## Parent` + intro + four `### S0..S3` yields chunks starting `["## Parent", "### S0", "### S1", "### S2", "### S3"]`; sub-chunks lose the parent heading. Pin deliberately.
  - `should recurse when a sub-heading piece is itself still oversized` — the `result.extend(_ensure_size(piece))` recursion.

### Phase 4: Oversized split with no headings (`_split_by_paragraphs`, 0% covered today)

- [x] **Task 7: `_split_by_paragraphs` — paragraph grouping**
  Files: `tests/knowledge/test_chunker.py`
  Test cases:
  - `should group whole paragraphs up to the limit when an oversized section has no sub-headings` — verified: a `## X` section of three ~900-char paragraphs (2707 chars) yields chunks of 1806 and 899 chars; assert each chunk is a whole number of paragraphs.
  - `should never cut inside a paragraph when grouping` — assert every emitted chunk starts and ends on a source paragraph boundary, and that each chunk's paragraph list is a contiguous slice of the source's paragraphs (do not rely on `_ends_at_boundary` — paragraph chunks don't end in headings).
  - `should keep a single over-limit paragraph intact rather than cut it mid-sentence` — verified: `"## X\n" + "a"*2500` returns one chunk of 2505 chars; the `if current and ...` guard. Confirms chunks may exceed `MAX_CHUNK_CHARS`.
  - `should still split an oversized section that contains no sentence terminator when it has paragraph breaks` — guards against a future switch to sentence-regex splitting; splitting is structural (heading/blank-line), not lexical.
  - `should treat a blank line containing only spaces or tabs as a paragraph separator` — `re.split(r"\n\s*\n", ...)`.

### Phase 5: Fenced code blocks (highest-value uncovered branch)

- [x] **Task 8: `_fenced_spans` / `_headings` — fence gating of heading decisions**
  Files: `tests/knowledge/test_chunker.py`
  Test cases:
  - `should not treat a # comment line inside a fenced backtick block as a heading` — verified: `## A` / fenced `sh` block with `# not a heading` / `## B` → 2 chunks, not 3.
  - `should ignore heading-like lines inside a ~~~ fenced block` — `_FENCE_RE` accepts both markers.
  - `should not close a backtick fence with a tilde fence` — `_fenced_spans` requires `marker == open_marker`.
  - `should recognize a fence indented up to three spaces and not treat a four-space-indented fence as a fence` — the `[ \t]{0,3}` bound; paired positive/negative.
  - `should recognize a fence opened with an info string and more than three backticks` — `` `{3,} `` plus `match.group(1)[0]`.
  - `should swallow the rest of the document when a fence is never closed` — verified: `"## A\n```\ncode\n\n## B\nb\n"` returns **1** chunk; `## B` disappears as a boundary. Pin explicitly and comment that this silent merge is deliberate current behaviour, not a regression.

### Phase 6: Line endings and whitespace

- [x] **Task 9: `chunk_markdown` — CRLF and trailing whitespace**
  Files: `tests/knowledge/test_chunker.py`
  Test cases:
  - `should split sections normally when the document uses CRLF line endings` — `.*$` under `re.MULTILINE` absorbs the `\r` into the heading line; assert `"## A"` as a substring/prefix, not exact equality with an `\n`-normalized string.
  - `should preserve trailing whitespace inside a chunk while still dropping an all-whitespace tail piece` — the `piece.strip()` filter vs. in-chunk whitespace retention.

### Phase 7: Output list contract (`chunk_index` dependency)

- [x] **Task 10: `chunk_markdown` — order, contiguity and losslessness**
  Files: `tests/knowledge/test_chunker.py`
  Test cases:
  - `should return chunks in source order` — assert each chunk's first-occurrence offset in the source is strictly increasing; `chunk_index` is positional in `PgVectorStore.upsert`.
  - `should return chunks whose concatenation reproduces the source exactly on the heading path` — verified: `"".join(chunk_markdown("## A\nx\n\n## B\ny\n")) == source`; catches content loss and duplication in the slice arithmetic.
  - `should not duplicate any content across chunks on the paragraph path` — assert every source paragraph appears in exactly one chunk (the paragraph path drops blank-line separators, so concatenation is not identity).
  - `should return no blank or whitespace-only chunk for any input` — a property-style sweep over the module's fixtures; a blank chunk would still consume a `chunk_index` and be embedded.
