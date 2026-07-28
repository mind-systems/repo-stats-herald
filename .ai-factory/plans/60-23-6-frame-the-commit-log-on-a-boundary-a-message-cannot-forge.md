# Plan: 23.6 — Frame the commit log on a boundary a message cannot forge

## Context
The commit-log parser frames records on a record-separator byte (`\x1e`) that git accepts inside a commit message, so a subject or body carrying it silently splits the record into sub-five-field fragments and the whole commit vanishes from the parsed context. This re-anchors the record boundary on NUL — the one byte git refuses in a commit message — so no message content can forge a boundary, and lands the record-separator test case with the fix.

## Design decision (the framing form)

The spec leaves the exact form open (a NUL-based boundary, or an RS that only counts when followed by a valid record head) but requires the result be *unforgeable*, not sanitised. An RS-plus-40-hex head is still author-controllable from inside a message, so this plan takes the **NUL-anchored** form, which rests on a byte a message provably cannot contain:

- **Pretty format:** replace the leading record marker `%x1e` with `%x00`. Each record's git output becomes `\x00<H>\x00<an>\x00<s>\x00<b>\x00<tail>`, where `<tail>` is the `--numstat`/`--shortstat` block. The next record's leading `\x00` doubles as the terminator of the previous record's tail.
- **Record finding:** because a commit message cannot contain NUL, a filesystem path cannot contain NUL, and the numstat/shortstat tail contains none either, the *only* NUL bytes in the whole log are the ones git emits from `%x00`. Splitting the log on NUL therefore yields a clean, uniform stream of exactly five fields per record (`H, an, s, b, tail`), preceded by one empty leading field from the very first record's `%x00`. `parse_log` splits on NUL, drops the single leading empty field, and regroups the stream into fixed groups of five, reconstructing each record as `\x00`-joined text and handing it to `_parse_record` **unchanged**.

Why this satisfies every guard: `_parse_record` still receives `H\x00an\x00s\x00b\x00tail` and still splits it with `maxsplit=4` into five parts, so field splitting, numstat/shortstat reading, subject-and-body joining and the requested-field set are all untouched — only *how records are found* changes. An `\x1e` byte in a subject or body is now ordinary field content and is preserved verbatim. No unquoting or escaping layer is added. `parse_log`'s signature and `collect`'s behaviour are unchanged.

## Settings
- Testing: yes
- Logging: minimal
- Docs: no

## Tasks

### Phase 1: Re-anchor the record framing on NUL

- [x] **Task 1: Change the record marker in `_PRETTY_FORMAT` from RS to NUL**
  Files: `src/commits/collector.py`
  Change `_PRETTY_FORMAT` from `"%x1e%H%x00%an%x00%s%x00%b%x00"` to `"%x00%H%x00%an%x00%s%x00%b%x00"` (leading `%x1e` → `%x00`; the four field `%x00` and the trailing `%x00` after `%b` are unchanged). Do not touch the `_run_log` invocation otherwise — `--numstat`, `--shortstat`, `-c core.quotepath=false`, `--end-of-options`, `text=True`, `check=True` and the requested fields all stay exactly as they are. Update the literal-placeholder comment above `_PRETTY_FORMAT` (lines 7–10) to describe the new NUL-only framing instead of `%x1e`/RS; keep the note that these must stay literal text (embedding a real NUL in the CLI argument would break process creation).

- [x] **Task 2: Rewrite `parse_log`'s record-finding to split on NUL and regroup by five** (depends on Task 1)
  Files: `src/commits/collector.py`
  Replace the current `for record in log_text.split(_RECORD_SEP):` loop. New behaviour:
  - Split `log_text` on `_FIELD_SEP` (`\x00`) into a flat field list.
  - The format prefixes the whole stream with one NUL, so the first field is an empty leading fragment — drop a single leading `""` field if present.
  - Group the remaining fields into consecutive chunks of five (`H, an, s, b, tail`). Reconstruct each record as `_FIELD_SEP.join(group)` and pass it to `self._parse_record(record)` **unchanged**; append the result when not `None`. A trailing chunk of fewer than five fields (should not occur for well-formed git output) reconstructs to fewer than five parts and `_parse_record` already returns `None` for it — rely on that rather than adding new validation. Return `CommitContext(repo=repo, branch=branch, commits=tuple(commits))` exactly as today.
  - Empty input (`log_text == ""`) must still yield an empty commit tuple without raising: `"".split("\x00")` is `[""]`, the leading-empty drop leaves no fields, and no records are produced.
  - Leave `_parse_record` and `_parse_tail` byte-for-byte unchanged. Do not touch subject/body joining, field separation, or numstat/shortstat reading.

- [x] **Task 3: Remove the now-unused `_RECORD_SEP` constant** (depends on Task 2)
  Files: `src/commits/collector.py`
  Delete `_RECORD_SEP = "\x1e"` — it has no remaining reference (confirmed: it was used only inside the old `parse_log` split). Keep `_FIELD_SEP = "\x00"`. Update the adjacent comment (lines 12–14) so it no longer describes an RS record separator, only the NUL field/record framing actually used.

### Phase 2: Land the record-separator test case

- [x] **Task 4: Add tests proving an `\x1e` byte in a message no longer drops the commit** (depends on Task 2)
  Files: `tests/commits/test_collector.py`
  Add two tests exercising the defect end-to-end through the real-repo fixtures (`git_repo`, `commit_at`, `collector`, and the module-level `_git` helper), matching the spec's verification. This is a silent-failure surface (a commit vanishes with no error), so it must be covered.
  - **should keep a commit whose subject contains the record-separator byte** — create an ordinary first commit, then a second commit whose subject carries a literal `\x1e` (commit via the module-level `_git` helper with pinned `user.name`/`user.email`, e.g. `_git("-c", "user.name=herald-test", "-c", "user.email=herald@test.invalid", "commit", "-q", "--allow-empty", "-m", "sub\x1eject", cwd=git_repo)`; git accepts RS in a message — verified in the spec). Run `collector.collect(str(git_repo), "HEAD")`, assert `len(ctx.commits) == 2` (both commits present, newest-first), and assert the crafted commit's `message` contains the `\x1e` byte intact.
  - **should keep a commit whose body contains the record-separator byte** — same shape, but place the `\x1e` in the body rather than the subject (two `-m` arguments, e.g. `-m "subject"` then `-m "bo\x1edy"`, so git forms `subject\n\nbo\x1edy`). Assert both commits parse and the byte survives in the crafted commit's `message`.
  - Do not edit or move any of the twelve existing tests; these are strictly additive. If any existing test needs changing to stay green, the framing change reached further than intended — stop and revisit Tasks 1–3.
