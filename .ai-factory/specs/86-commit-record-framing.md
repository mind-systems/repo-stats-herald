# 23.6 — Frame the commit log on a boundary a message cannot forge

**Phase:** 23 — Clear the way for the coverage pass. Independent of 23.5 and of the four seams, though it lands in the same file as 23.1 and 23.2. Owns the record-separator case in `.ai-factory/specs/77-commit-collector-parse-test-plan.md`, which that plan records as out of scope precisely because the behaviour it asserts does not exist yet.

## Current state

The commit log is requested with a pretty format that prefixes every record with a record-separator byte, and `parse_log` recovers the records by splitting the text on that byte. Within a record the four fields — commit id, author, subject, body — are separated by NUL, and `_parse_record` requires five parts before it will build a commit.

Nothing stops that separator byte from appearing inside a commit message. Confirmed against real git: a subject carrying it is accepted and stored verbatim, and the byte then arrives in the log text indistinguishable from a genuine record boundary. The record splits into two fragments, each holding fewer than five NUL-separated fields, `_parse_record` returns nothing for both, and the commit disappears from the parsed context. Confirmed by running the parser: two records in, one commit out, no error and no log line.

The consequence is a commit missing from every narration built over that range — the summary, the linked change's commit detail, the reports, the release note — while the surrounding commits parse normally, so the output looks complete. It is also a way to remove a commit from the record deliberately, since the byte is something an author controls.

The fix has an anchor. Confirmed against real git: a NUL byte in a commit message is refused outright — `a NUL byte in commit log message not allowed` — so NUL is the one byte a message cannot carry, and any framing that rests on it, or on something equally unforgeable, cannot be spoofed from inside a message.

## Change

Make the record boundary one a commit message cannot produce, and land the record-separator case from the test plan with it. Which form that takes is this task's decision against the constraint above — a NUL-based boundary, or a separator that only counts as one when followed by what must begin a record, are both open. What is not open is leaving a boundary a message can contain.

## Files & types

- edit `src/commits/collector.py` (the pretty format, and the record framing in `parse_log`)
- add the record-separator case to the collector's parse tests

## Guards

- `parse_log`'s signature and `collect`'s behaviour are unchanged; this changes how records are found, not what a record parses into.
- The field separation, the numstat and shortstat reading, and the subject-and-body joining are untouched, and the set of fields requested from git does not change.
- Every existing collector test stays green with no edit. If one has to move, the framing change reached further than it should have.
- A body carrying the byte is covered as well as a subject — both are message content and both reach the same split.
- No unquoting or escaping layer is introduced to compensate; the boundary is made unforgeable rather than the content sanitised.

## Verification

- A two-record log text whose second subject carries the old separator byte yields two commits, with the subject intact including the byte.
- The same holds when the byte is in the body rather than the subject.
- An ordinary range over a real repository parses exactly as it does today.
- The twelve existing collector tests and the parse-group tests all pass unchanged.
