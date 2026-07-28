# Code Review: 23.1 — Read git paths in the encoding Python expects

## Scope
Single change in `src/commits/collector.py`: `_collect_commits` now runs its `git log --numstat --shortstat` invocation with `-c core.quotepath=false` inserted immediately after `self._git_bin`.

## Verification against spec and guards

- **Correct placement and form.** The `-c` / `core.quotepath=false` pair sits before `-C repo_path`, byte-identical to the already-correct sibling `changed_paths` (collector.py:82–99). Git config flags must precede the subcommand; they do.
- **Only the invocation changed.** `_parse_tail`, `_parse_record`, `_NUMSTAT_RE`, `_SHORTSTAT_RE`, and the `_RECORD_SEP`/`_FIELD_SEP` framing are untouched — confirmed by the diff (a 2-line insertion, nothing else).
- **No unquoting logic added.** The embedded-newline/quote case remains out of scope, as required.
- **All-ASCII output unchanged.** `core.quotepath=false` only affects rendering of bytes outside printable ASCII; an all-ASCII repo produces byte-identical output. Captured eval output does not shift.
- **`changed_paths` not edited.** Correct.
- **Consistency achieved.** A collected `changed_files` entry for a non-Latin path now equals what `changed_paths` reports and what `SourceStrategy.selects` / `read_blob` expect.

## Runtime considerations
- Output is captured with `text=True`; with quoting disabled git emits raw UTF-8 path bytes, which decode cleanly under the default UTF-8 text mode. No new decode-error surface is introduced (the numstat regex still matches literal path text).
- No migrations, schema, type, or concurrency surfaces are involved.
- Leaves the invocation clean for 23.2 to build on, as noted.

No findings.

REVIEW_PASS
