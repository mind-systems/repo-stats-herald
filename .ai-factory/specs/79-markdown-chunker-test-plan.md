# Markdown Chunker — Test Plan

**Date:** 2026-07-29
**Source:** roadmap-test-coverage agent

## Source Overview

`src/knowledge/chunker.py` (129 lines) exposes one public function, `chunk_markdown(text) -> list[str]`, plus `MAX_CHUNK_CHARS = 2000` and four private helpers: `_headings`, `_fenced_spans`, `_split_at_min_level_headings`, `_split_by_paragraphs`. It splits a Markdown document at its **shallowest** ATX heading level so each chunk is a whole section (heading + body); a section over `MAX_CHUNK_CHARS` is re-split on its nested sub-headings, and if it has none, on blank-line paragraph boundaries — never mid-sentence. The output list order *is* the `chunk_index` sequence: `PgVectorStore.upsert` assigns `chunk_index` by `enumerate` position, and `(repo, path, chunk_index)` is the table's primary key, so a reordering or duplication bug here silently corrupts retrieval identity.

## Instantiation

**No instantiation, no mocking, no fixtures.** `chunk_markdown` is a module-level pure function over a `str`, with no I/O, no clock, no randomness, no collaborators — the governing spec's own guard says "Pure, no I/O … operate on paths/text already in hand, so the red tests run without a mirror or store" (`.ai-factory/specs/43-source-strategy-chunker-contract.md`). Every test is `chunks = chunk_markdown(<literal string>)` followed by assertions on the returned list. That makes this area unusually cheap to cover exhaustively: there is no setup cost per case, so branch-complete coverage is a matter of writing enough string literals. Size-sensitive fixtures must be built against the imported `MAX_CHUNK_CHARS`, never against a hard-coded `2000`.

## Existing Coverage

`tests/knowledge/test_chunker.py` has exactly two tests for the 129 lines:

1. `test_chunk_markdown_splits_into_one_chunk_per_heading_section` — a three-`##` document, all sections under the limit, no preamble, no nested sub-headings. Pins only the flat, uniform, happy path.
2. `test_chunk_markdown_splits_oversized_section_without_cutting_mid_sentence` — one `##` section padded with `###` sub-heading paragraphs until it exceeds `MAX_CHUNK_CHARS`; asserts `len(chunks) > 1` and that every chunk ends either on a heading line or on `.`/`!`/`?`. Exercises only the sub-heading branch of `_ensure_size`.

**Left completely open:** the preamble branch (`starts[0] > 0`); the no-heading branch (`sections is None` → `[text]`); empty/whitespace-only input (`→ []`); the blank-chunk filter; the min-level selection rule; the exact `<= MAX_CHUNK_CHARS` boundary; the entire `_split_by_paragraphs` last-resort path (never reached by either test); the oversize-with-no-terminator fallback; **the whole `_fenced_spans` code-fence machinery** (~22 lines, zero coverage); CRLF and trailing-whitespace handling; setext headings; and any assertion on order/contiguity/lossless-ness of the returned list. The `_ends_at_boundary` helper is also weaker than it reads — a chunk ending in a `###` heading line passes it trivially, so it does not actually prove no-mid-sentence for the paragraph path.

## Test Cases

### Section boundary detection (the core contract)

- **should return one chunk per top-level heading section when the document has several same-level headings** — already covered by test 1; keep as the regression anchor.
- **should keep a heading line and its body together in a single chunk when the section is under the limit** — assert on the chunk *text*: `chunks[0].startswith("## Section One")`.
- **should emit exactly one chunk when the document has a single `#` heading followed by several `##` sub-headings and totals under the limit** — `_split_at_min_level_headings` min-level rule. **Non-obvious:** verified behavior — `min_level` is 1, there is one split start at index 0, so the whole document is one chunk. The `##` headings do *not* start new chunks. This is the single most surprising rule in the module and is entirely unpinned today; a naive "split on every heading" refactor would break it silently.
- **should split at `###` level when the document's shallowest heading is `###`** — confirms the split level is relative (shallowest present), not absolute.
- **should not start a new chunk at a deeper heading when a shallower sibling follows it** — e.g. `## A / ### A1 / ## B`; expect 2 chunks, with `### A1` living inside chunk 0.
- **should treat text before the first heading as its own leading chunk** — the `starts[0] > 0` branch.
- **should return the whole document as one chunk when it contains no headings and fits the limit** — the `sections is None` → `[text]` branch.
- **should not treat a `#` with no space after it as a heading** — `_HEADING_RE` requires `#{1,6}[ \t]+\S`; `#hashtag` and a bare `#` line are body text.
- **should not treat a 7+ `#` run as a heading** — `#######` exceeds the `{1,6}` bound.

### Empty and degenerate input

- **should return an empty list when the input is the empty string** — the `text.strip()` guard. Verified: `[]`.
- **should return an empty list when the input is only whitespace and newlines** — verified `"   \n\n  "` → `[]`.
- **should keep a heading with an empty body as its own chunk** — `"## A\n## B\n"` → verified `["## A\n", "## B\n"]`. Confirms the final `if chunk.strip()` filter does not eat heading-only sections (an empty section still becomes a real row with a real `chunk_index`).
- **should drop a whitespace-only trailing piece rather than emit a blank chunk** — the terminal list comprehension and the `piece.strip()` filter.

### Size threshold (`MAX_CHUNK_CHARS`)

- **should return the section as a single chunk when it is exactly `MAX_CHUNK_CHARS` long** — `_ensure_size` (`<=` branch). **Non-obvious setup:** build the string to exact length by padding against `MAX_CHUNK_CHARS` and assert `len(section) == MAX_CHUNK_CHARS` before calling, so the fixture can't drift.
- **should split a section that is one character over `MAX_CHUNK_CHARS` when it has splittable structure** — pair it with the exact-length case so the two together pin the boundary from both sides; a `<` vs `<=` flip must fail one of them.
- **should split an oversized section on its nested sub-headings** — currently covered by test 2; strengthen it to assert *which* pieces come out, not merely `len > 1`.
- **should keep the parent heading only on the leading piece when an oversized section is split on sub-headings** — **Verified behavior:** `## Parent` + intro + four `### S0..S3` yields chunks starting `["## Parent", "### S0", "### S1", "### S2", "### S3"]` — the sub-chunks lose the parent heading. Pin this deliberately: it is a real retrieval-context tradeoff, and pinning it makes any future "repeat the parent heading" change an explicit decision.
- **should recurse when a sub-heading piece is itself still oversized** — `_ensure_size` recursion via `result.extend(_ensure_size(piece))`.

### Oversized split with no headings (`_split_by_paragraphs` — currently 0% covered)

- **should group whole paragraphs up to the limit when an oversized section has no sub-headings** — verified: a `## X` section of three ~900-char paragraphs (2707 chars) yields chunks of 1806 and 899 chars. Assert each chunk is a whole number of paragraphs.
- **should never cut inside a paragraph when grouping** — assert every emitted chunk both starts and ends on a paragraph boundary present in the source. **Non-obvious:** the existing `_ends_at_boundary` helper is insufficient here because paragraph chunks don't end in headings; assert terminal punctuation *and* that each chunk's paragraph list is a contiguous slice of the source's paragraphs.
- **should keep a single over-limit paragraph intact rather than cut it mid-sentence** — the `if current and ...` guard. **Verified:** `"## X\n" + "a"*2500` returns one chunk of 2505 chars. This is the deliberate fallback: **`chunk_markdown` may return chunks longer than `MAX_CHUNK_CHARS`.** Any test asserting a universal `len(chunk) <= MAX_CHUNK_CHARS` would be wrong.
- **should still split an oversized section that contains no sentence terminator at all when it has paragraph breaks** — guards against a future implementation that switches to sentence-regex splitting and then silently returns one giant chunk (or `[]`) for terminator-free text such as a table or a bullet list.
- **should treat a blank line containing only spaces or tabs as a paragraph separator** — `re.split(r"\n\s*\n", ...)`.

### Fenced code blocks (the highest-value uncovered branch)

- **should not treat a `#` comment line inside a fenced code block as a heading** — verified: `## A` / fenced `sh` block containing `# not a heading` / `## B` → 2 chunks, not 3.
- **should ignore heading-like lines inside a `~~~` fenced block** — `_FENCE_RE` accepts both markers.
- **should not close a backtick fence with a tilde fence** — `_fenced_spans` requires `marker == open_marker`.
- **should recognize a fence indented up to three spaces** — `[ \t]{0,3}` in `_FENCE_RE`; and a paired case for a 4-space-indented fence which is *not* a fence.
- **should recognize a fence opened with an info string and more than three backticks** — `` `{3,} `` plus `match.group(1)[0]`.
- **should swallow the rest of the document when a fence is never closed** — verified: `"## A\n```\ncode\n\n## B\nb\n"` returns **1** chunk; `## B` disappears as a boundary. This is the module's sharpest silent-failure: a stray unmatched fence in a real `ARCHITECTURE.md` merges every following section into one chunk with no error. Pin the current behavior explicitly and label it so the merge is a known, chosen outcome rather than a regression discovered in retrieval quality months later.

### Line endings and whitespace

- **should split sections normally when the document uses CRLF line endings** — verified working. Non-obvious: `.*$` under `re.MULTILINE` absorbs the `\r` into the heading line, so the `\r` is retained in chunk text — assert on `"## A"` as a prefix/substring, not on exact equality with an `\n`-normalized string.
- **should not split at a heading that has trailing whitespace only after the `#`** — `#{1,6}[ \t]+\S` requires a non-space char.
- **should preserve trailing whitespace inside a chunk while still dropping an all-whitespace tail piece.**
- **should not treat a setext (`===` / `---`) underline as a heading** — verified: returns a **single** chunk. The implementation is ATX-only. Pin it as a known limitation: a setext-authored document is never section-split, so it silently becomes one (possibly oversized) unit.

### Output list contract (`chunk_index` dependency)

- **should return chunks in source order** — assert each chunk's first-occurrence offset in the source is strictly increasing. `chunk_index` is positional in `PgVectorStore.upsert`, so order is the identity contract.
- **should return chunks whose concatenation reproduces the source exactly on the heading path** — verified: `"".join(chunk_markdown("## A\nx\n\n## B\ny\n")) == source`. This one assertion catches both content loss and duplication in `_split_at_min_level_headings`'s slice arithmetic.
- **should not duplicate any content across chunks on the paragraph path** — weaker invariant for `_split_by_paragraphs` (which drops the blank-line separators): assert every source paragraph appears in exactly one chunk.
- **should return no blank or whitespace-only chunk for any input** — a property-style sweep over all fixtures in the module; a blank chunk would still consume a `chunk_index` and be embedded.

## Gotchas

- **Fenced code is the trap.** `_fenced_spans` is ~22 lines with zero current coverage and it gates *every* heading decision. Two behaviors matter and neither crashes: heading-like `#` comments inside a fence are correctly ignored (good), and an **unclosed** fence extends to end-of-text and suppresses every heading after it, merging the document tail into one chunk (dangerous). Real ai-factory artifacts under `.ai-factory/specs/**` and `docs/**` are dense with code fences, so this path runs constantly in production. Also note the fence marker must match in kind to close, and the open-fence indent tolerance is 0–3 spaces.
- **The `MAX_CHUNK_CHARS` boundary is `<=`, and the limit is not a guarantee.** `_ensure_size` returns `[section]` for `len == MAX_CHUNK_CHARS` and splits at `MAX_CHUNK_CHARS + 1`; test both sides against the imported constant, never a literal `2000`. But do **not** assert a global `len(chunk) <= MAX_CHUNK_CHARS` — `_split_by_paragraphs` deliberately emits an over-limit chunk when a single paragraph exceeds the limit (verified: 2505 chars), because cutting it would violate the "never mid-sentence" clause. The size limit is a target that yields to the sentence-integrity rule.
- **The no-terminator fallback is structural, not lexical.** Nothing in the implementation looks for `.`/`!`/`?`; "never mid-sentence" is achieved by only ever cutting at heading starts or blank-line paragraph breaks. So terminator-free content (tables, bullet lists, log dumps) splits fine on paragraph breaks and stays whole when there are none. The existing `_ends_at_boundary` helper tests a *proxy* for the real rule — new tests should assert boundary alignment against the source structure instead.
- **The min-level rule is counter-intuitive.** Splitting happens only at the shallowest heading level present, so a document with one `#` title and ten `##` sections under 2000 chars total produces **one** chunk, and an oversized section's sub-chunks lose their parent heading. Both are verified current behavior and both are unpinned; write them down before anyone "fixes" them.
- **This module has no I/O, no collaborators, and no mocks.** Every case above is a string literal and one call. Given the silent-failure blast radius, exhaustive coverage here is the cheapest reliability purchase in the knowledge pipeline.
