# Review: 23.6 — Frame the commit log on a boundary a message cannot forge

## Scope
Code changes in `src/commits/collector.py` (pretty format + `parse_log` record framing, `_RECORD_SEP` removal) and `tests/commits/test_collector.py` (two additive tests). Planning artifacts under `.ai-factory/` were not reviewed as code.

## What the change does
- `_PRETTY_FORMAT`: leading record marker `%x1e` → `%x00`, so every record is framed on NUL.
- `parse_log`: splits `log_text` on NUL, drops the single empty leading field, regroups the flat field stream into fixed chunks of five (`H, an, s, b, tail`), reconstructs each as `_FIELD_SEP.join(group)`, and hands it to `_parse_record` unchanged.
- `_RECORD_SEP` deleted; `_FIELD_SEP` retained. `_parse_record`/`_parse_tail`, the requested fields, and the git invocation flags are untouched.

## Correctness analysis
The design rests on the invariant that the *only* NUL bytes in the whole log are the five `%x00` per commit. That invariant is airtight: git refuses NUL in a commit message and in author ident, filesystem paths cannot contain NUL, and the numstat/shortstat tail contains none. So for N commits the output is exactly `5N+1` NUL-split fields — one empty leading field plus N groups of five — and grouping by five after dropping the leading empty maps each group to exactly the record `_parse_record` previously received via the RS split. The reconstructed record `H\x00an\x00s\x00b\x00tail` is byte-identical to the old post-RS-split record, so field splitting, subject/body joining, and numstat/shortstat reading are genuinely unchanged.

Because the only byte that changed in the emitted stream is each commit's leading marker (`\x1e`→`\x00`), and the tail already provably held no NUL, the new grouping is exact and cannot be forged from message content.

Edge cases checked:
- Empty range: `"".split("\x00")` → `[""]`, leading-empty drop → `[]`, no records, empty tuple — no raise.
- Empty body / empty-stat (allow-empty) commits: `%b` still contributes its field and the format still emits all five NULs, so the group count stays five; verified via a real allow-empty commit parsing as one commit with subject-only message.
- Trailing partial group (only possible on malformed/truncated output, which `check=True` in `_run_log` prevents): reconstructs to fewer than five parts and `_parse_record` already returns `None` — no crash, no misparse.
- The `fields[0] == ""` drop cannot misfire: the format guarantees the stream starts with the leading `\x00`, and a commit hash field is never empty.

## Verification performed
- `uv run pytest tests/commits/test_collector.py` → 14 passed (12 existing unchanged + 2 new). No existing test edited (diff is additive only), satisfying the guard.
- Real-git end-to-end run over a two-commit repo with a multi-file commit whose subject carries `\x1e` and a following body: both commits parsed, the `\x1e` byte preserved in the message (`X\x1eY\n\nbody line`), both changed paths captured (including a >40-char nested path and a path with a space), and the shortstat parsed correctly — confirming the numstat/shortstat tail still attaches to the right record under the new framing.

## Guard compliance
- `parse_log` signature and `collect` behaviour unchanged.
- Field splitting, numstat/shortstat reading, subject/body joining, and the requested-field set untouched.
- No unquoting/escaping layer introduced; the boundary is made unforgeable, not the content sanitised.
- Both subject-carries-byte and body-carries-byte are covered.

## Findings
None. The implementation is correct, matches the plan, and both the existing suite and a real-git exercise of the numstat tail confirm no regression.

REVIEW_PASS
