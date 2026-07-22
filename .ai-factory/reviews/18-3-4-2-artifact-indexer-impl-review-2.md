# Code Review (re-review): 3.4.2 — Artifact indexer (impl)

Re-review after fixes to review-1. Re-read all changed files in full via `git diff HEAD` + `Read`; ran the red tests through `uv run pytest`.

## Verdicts on previous findings

### Finding 1 — `chunk_markdown` treats `#` comment lines inside fenced code blocks as headings → **Fixed**

The chunker now detects fenced regions and excludes any heading whose start falls inside one.

`src/knowledge/chunker.py:6`:
```python
_FENCE_RE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})", re.MULTILINE)
```
`src/knowledge/chunker.py:32-37` (`_headings`):
```python
    fenced = _fenced_spans(text)
    return [
        (match.start(), len(match.group(1)))
        for match in _HEADING_RE.finditer(text)
        if not any(start <= match.start() < end for start, end in fenced)
    ]
```
`src/knowledge/chunker.py:40-61` (`_fenced_spans`) tracks open/close fence lines (matched by marker char), spanning an unclosed fence to end-of-text.

**Evidence it resolves the reported failure:** running the current `chunk_markdown` over the real `CLAUDE.md` (a selected artifact whose ```` ```bash ```` block contains `# 1.`/`# 2.`/`#   ...` comment lines) now yields 9 chunks split on the real `##`/leading sections — `## Architecture`, `## Patterns to follow`, `## Verification`, `## Logging`, `## Documentation` are each their own chunk, no longer swallowed into a code-comment "heading," and the fence is not torn. Previously the top-level split collapsed to `min_level=1` on those comment lines.

**Regression check:** `uv run pytest tests/knowledge/test_chunker.py tests/knowledge/test_source_strategy.py` → **18 passed**. The two red-test files stay green (fence-free fixtures are unaffected — `_fenced_spans` returns `[]` for them).

## New issues

None.

I checked whether the fence logic introduces new defects:

- **Recursive slices stay consistent.** `_split_at_min_level_headings` recurses on section slices, and `_headings`/`_fenced_spans` recompute fences per slice. Because split points are only ever real headings (fenced `#` lines are excluded as split candidates), a section boundary never falls inside a fence — so every fenced block lies wholly within one section, and per-slice fence recomputation cannot desync or tear a fence across chunks.
- **Mixed/nested markers** (```` ``` ```` opened, `~~~` inside) are correctly ignored as closers because the close must match the opening marker char (`chunker.py:55`).
- **Unclosed fence** spans to end-of-text (`chunker.py:59-60`); on a well-formed artifact this never triggers, and on a malformed one it fails safe (no false headings) rather than crashing.
- **Unchanged files** `indexer.py` and `source_strategy.py` are byte-identical to review-1, where they were assessed clean (constructor DI, `zip(strict=True)` guarding chunk↔embedding alignment, empty-chunk path still clears via `upsert`, correct selection for every parametrized path). No re-review concerns.

## Non-issues (carried, still acceptable by design)

- `_split_by_paragraphs` may emit a chunk `> MAX_CHUNK_CHARS` for a single blank-line-free oversized paragraph — intentional ("never mid-sentence" wins over size).
- `(tree / path).read_text` raises `FileNotFoundError` if a selected path is absent — fail-loud, caller-controlled (3.6).

REVIEW_PASS
