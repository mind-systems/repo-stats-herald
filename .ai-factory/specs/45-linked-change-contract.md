# 4.2.1 — Linked-change contract + resolve tests (red)

**Phase:** 4 — Episodic memory (the evolution log). Owned by episodic — this produces the episodic unit; the narrator — now the reasoner (Phase 8) — consumes it, but does not own it. First half of the resolver milestone — the type + contract, pinned with red tests, ahead of the implementation (4.2.2).

## Current state

A push is a range of commits (`PushEvent` from task 2.1; the mirror pulled to `after` by Phase 3's `KnowledgeSync`). Phase 1's `GitCommitCollector.collect(repo_path, rev_range)` reads local `git log --stat`. Nothing yet extracts the *intent + outcome* a change delivers — the roadmap tasks it completed — from the change, and nothing pins the correct semantics before an implementation is written. `LinkedChange` is consumed by nearly every downstream task (4.1.2's writer, 4.4's backfill, 5.4, 8.1's narrate, 10.1's report builder, 11.2's release note), so a mis-resolved change silently poisons all of them.

The trap: a naive "added `+[x]` diff lines" parser produces a **false positive** — a task line that was already `[x]` before the range, then merely **moved or reformatted** (reordered under a renumbered phase, reworded, reindented) within the same range, shows up in the diff as an added `+[x]` line and gets counted as newly completed, even though it delivered nothing new in this range.

## Change

Define the `LinkedChange` type and the `resolve()` signature, and pin the correct resolution semantics with red tests before writing the parsing logic.

- `src/episodic/linked_change.py`:
  - `LinkedChange` (immutable): `repo: str`, `completed_tasks: tuple[str, ...]`, `commits: CommitContext`.
  - A STUBBED `resolve(repo: str, before: str, after: str) -> LinkedChange` (raises `NotImplementedError` for now).
- Write red tests pinning:
  - a genuine become-done task — absent or `[ ]` in the roadmap at `before`, `[x]` at `after` — appears in `completed_tasks`;
  - a **relocated already-done line** — `[x]` in the roadmap at both `before` and `after`, but moved/reformatted within the range — does **NOT** appear in `completed_tasks` (no false positive from raw added-line diffing);
  - the roadmap path is read from the source strategy (default `ROADMAP.md`; `.ai-factory/ROADMAP.md` if present), not hardcoded;
  - no roadmap, or no genuine done-transition in the range → `completed_tasks` empty, falls back to commits-only, never crashes;
  - merge commits and empty ranges resolve without error.

## Files & types

- new `src/episodic/__init__.py`, `src/episodic/linked_change.py` (`LinkedChange`, stub `resolve`)
- new test file(s) covering the cases above (red)

## Guards

- Tests-first: the stub raises rather than parsing — 4.2.2 turns these tests green, never the reverse.
- The relocated-line test is explicit and adversarial (a planted already-`[x]` line that moves within the range) — a test that only checks the happy-path transition would not catch the false-positive trap.
- Reads the local mirror only — no network fetch (asserted by the test setup, not by this task's own I/O, since it's stubbed).

## Verification

- The test suite added here is red against the stub (fails only because `resolve` has no logic yet).
- Each of the five pinned cases (genuine transition, relocated-line non-match, source-strategy path, empty/no-roadmap fallback, merge/empty-range safety) has a corresponding red test.
