# Code Review: commits/ feature (03-commits-feature)

## Summary

**Files reviewed (in full):** `src/commits/__init__.py`, `src/commits/models.py`, `src/commits/collector.py`, plus context: `src/main.py`, `src/core/config.py`, `pyproject.toml`, `Makefile`, plan `03-commits-feature.md`.
**Risk level:** 🟢 Low
**Verdict:** Implementation matches the plan and the spec note. All plan guards were exercised against live git and hold. No bugs that break the milestone's stated behavior. One minor, non-blocking fidelity note (non-ASCII paths).

The code was run end-to-end, not just read.

---

## Behavior verified at runtime

- **Primary verify (`collect(".", "HEAD~3..HEAD")` on this repo):** returns a `CommitContext` with `branch="main"`, 3 `Commit`s, each with non-empty `sha`/`author`/`message` and **full, untruncated** paths (e.g. `.ai-factory/plan-reviews/02-settings-layer-plan-review-1.md`, no leading `...`). `diffstat` is the clean `--shortstat` line. The review-1 path-truncation concern is genuinely resolved by `--numstat --shortstat`.
- **Empty range (`HEAD..HEAD`):** exits 0, empty output → `commits == ()`. No crash. ✓
- **Merge commit:** no per-file stats emitted (no `-m`) → `changed_files == ()`, `diffstat == ""`, no crash. ✓
- **Rename:** rendered as `f.txt => renamed.txt` and kept whole, as the plan specifies. ✓
- **Empty-body commits** (`root`, `Roadmap update`): `message` falls back to the subject; the trailing-NUL body field parses to `""` without breaking record shape. ✓
- **Malformed/unknown range (`HEAD~5..HEAD` where `HEAD~5` doesn't exist):** `git log` exits 128 → `CalledProcessError` propagates. Matches the plan's "fail loud on a bad range." ✓

## Correctness notes (confirmed sound)

- **Record/field parsing is robust.** The body is delimited by its own NUL and captured as `parts[3]` with `split(_FIELD_SEP, 4)`; the stat block is the 5th field. A commit body containing newlines — or a line that *looks* like a numstat/shortstat line — cannot leak into file parsing. Verified logically and by the multi-line-body commits in this repo.
- **numstat vs shortstat never cross-match.** `_NUMSTAT_RE` requires two tab-separated numeric-or-`-` columns; `_SHORTSTAT_RE` requires `N file(s) changed` with no tabs. A file literally named `3 files changed` is still matched by the numstat branch first (it has tab columns) and `continue`s, so it can't be mistaken for the summary line.
- **Binary files** (`-\t-\tpath`) are handled by the `(?:\d+|-)` alternation; the path column is still captured.
- **Leading empty record** from the RS-prefixed stream is dropped by the position-agnostic `if not record.strip(): continue`, as the plan required.
- **Security/guards:** argument list (no `shell=True`), `--end-of-options` before `rev_range`, only `log` + `rev-parse` (read-only), `-C` never changes cwd, no network. All match the plan.
- **Imports** use `from src.commits.models import ...`, consistent with the `src.main:app` package root (`uvicorn src.main:app`). No import-path mismatch.
- **Models** are `@dataclass(frozen=True, slots=True)` with `tuple[...]` fields — immutable/hashable, matching the py3.12 style in `src/core/config.py`.

---

## Minor / non-blocking

**M1 — Non-ASCII paths come back octal-escaped and quoted (fidelity, out of this milestone's scope).**
`src/commits/collector.py:_parse_tail`. With git's default `core.quotePath=true`, a path containing non-ASCII bytes is emitted by `--numstat` as a C-quoted, octal-escaped string. Confirmed live: a file `café.txt` lands in `changed_files` as `'"caf\\303\\251.txt"'` (paths with spaces are unaffected — `space name.txt` comes through clean). So for non-ASCII filenames, `changed_files` holds the escaped/quoted form rather than the real path — the same class of "looks fine, subtly not the real path" issue the review flagged for `--stat`, but limited to non-ASCII names.

This does **not** break the milestone: it never crashes, ASCII paths (the verify case and the overwhelming majority of code repos) are full and untruncated, and the spec note/plan did not call out non-ASCII path handling. It's a latent data-quality item for the downstream summarizer. If desired later, pass `-c core.quotePath=false` (and/or `-z` for NUL-terminated paths) to get raw UTF-8 paths — a natural fit for the future "Structure-aware context collection" phase rather than this one.

---

## Conclusion

The implementation is correct, well-scoped, and passes every guard and the verify step from the plan under live execution. The only observation (M1) is a minor, non-blocking fidelity nuance for non-ASCII filenames that is outside this milestone's stated scope and degrades gracefully. Cleared for the orchestrator.

REVIEW_PASS
