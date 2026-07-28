## Plan Review Summary

**Plan:** `.ai-factory/plans/61-markdown-chunker.md` — test plan pinning the full contract of `chunk_markdown` (`src/knowledge/chunker.py`)
**Governing spec:** `.ai-factory/specs/79-markdown-chunker-test-plan.md` (via `ROADMAP_TESTS.md` → "Markdown chunker")
**Risk Level:** 🟢 Low

### Context Gates
- **Architecture** (`.ai-factory/ARCHITECTURE.md`): PASS — the plan is test-only, adds no code, introduces no cross-feature dependency, and touches only `tests/knowledge/test_chunker.py`. No boundary implications.
- **Rules** (`.ai-factory/RULES.md`): PASS — no test/pytest conventions defined; nothing to violate. The plan's guard to keep pinning-comments free of any plan/roadmap/spec reference matches the global "comments never cite the plan layer" rule.
- **Roadmap** (`.ai-factory/ROADMAP_TESTS.md`): PASS — the plan maps cleanly to the "Markdown chunker" task and honors its stated guards verbatim (build size fixtures against the imported constant; do not assert a universal upper bound; pin the unclosed-fence merge as current behaviour). Spec `79-markdown-chunker-test-plan.md` is the correct leaf.
- **Governing-spec conformance**: PASS — all 37 test cases in spec 79 are present across the plan's 10 tasks (verified case-by-case). Nothing dropped; the phase grouping is a faithful reorganization, not a reduction. Spec case "heading with trailing whitespace only after `#`" is folded into Task 3's "heading marker followed only by whitespace" case — same `#{1,6}[ \t]+\S` behaviour, correctly placed.

### Critical Issues
None.

### Verification of "verified" claims
Every behavioural/numeric assertion the plan relies on was re-checked by executing the actual module, not taken on faith:

- Empty `""` → `[]`; whitespace-only `"   \n\n  "` → `[]` — confirmed.
- `"## A\n## B\n"` → `["## A\n", "## B\n"]` (heading-only sections survive the `chunk.strip()` filter) — confirmed.
- `"## X\n" + "a"*2500` → one chunk of **2505** chars (over-limit single paragraph kept intact) — confirmed; validates the "no universal `<= MAX_CHUNK_CHARS`" guard.
- Unclosed fence `"## A\n```\ncode\n\n## B\nb\n"` → **1** chunk (`## B` swallowed) — confirmed; correctly flagged as deliberate silent merge.
- Setext underline → single chunk (ATX-only) — confirmed.
- `#hashtag` (no space) and `#######` (7 `#`) → body text, not headings — confirmed.
- Single `#` + several `##` under limit → **1** chunk (min-level rule) — confirmed.
- Parent-heading loss: `## Parent` + four `### S0..S3` (oversized) → chunk heads `["## Parent","### S0","### S1","### S2","### S3"]` — confirmed.
- Exact-`MAX_CHUNK_CHARS` section → 1 chunk; one char over *with sub-heading structure* → splits (the `<=` vs `<` boundary is pinned from both sides) — confirmed.
- Blank line of spaces as paragraph separator (`re.split(r"\n\s*\n", ...)`) — confirmed.
- CRLF: `\r` absorbed into the heading line; `"## A"` survives as a prefix — confirmed (plan correctly instructs substring/prefix assertion, not exact `\n`-normalized equality).

### `chunk_index` grounding
The Phase 7 rationale is real: `PgVectorStore.upsert` assigns `chunk_index` by `enumerate` position (`src/knowledge/store.py`), and `(repo, path, chunk_index)` is the primary key — so the order/contiguity/losslessness assertions defend an actual identity contract, not a hypothetical one.

### Positive Notes
- Guards are precise and defend against the exact refactor traps that would pass a naive test: the min-level rule, the `<=` boundary, the over-limit-paragraph exception, and the structural (not lexical) "never mid-sentence" mechanism are each pinned with a rationale.
- The plan correctly recognizes the existing `_ends_at_boundary` helper is a weak proxy on the paragraph path and specifies a stronger contiguous-slice assertion instead (Task 7).
- Test command (`uv run pytest tests/knowledge/test_chunker.py`), target file, and imported constant are all correct against the codebase.
- Deliberately-wrong behaviours (unclosed-fence merge, setext-blindness, parent-heading loss) are pinned as current behaviour with the instruction to comment them, turning any future change into an explicit decision — the right call for a coverage-hardening task.

### Minor (non-blocking)
- Task 7's illustrative sizes "1806 and 899 chars" (carried from the spec) are paragraph-size-dependent; a run with exact-900-char paragraphs yields 1802/900. This is harmless because the plan specifies the robust assertion — "each chunk is a whole number of paragraphs" — rather than the literal byte counts. No change required; noted only so the implementer treats those numbers as illustrative.

PLAN_REVIEW_PASS
