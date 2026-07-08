# 4.2.2 — Linked-change resolver (impl)

**Phase:** 4 — Episodic memory (the evolution log). Depends on 4.2.1 (the `LinkedChange` type, the `resolve` signature, and its red tests — including the relocated-line false-positive trap). Second half of the resolver milestone — turns 4.2.1's tests green.

## Current state

4.2.1 defines `LinkedChange` and stubs `resolve(repo, before, after)`, pinning the correct completion semantics (set-difference of done-markers, not raw added-line diffing) with red tests. The stub raises for every call — no roadmap comparison, no commit collection exists yet.

## Change

Implement `resolve` using **set-difference semantics**: completed tasks are the roadmap's done-marker set in `after` minus the done-marker set in `before` — comparing the two full versions of the roadmap across the range, not scanning the diff for added `+[x]` lines. This is robust to a task line that was already done and merely moved or was reformatted within the range (it appears in both sets, so it cancels out of the difference).

- `src/episodic/linked_change.py`:
  - `resolve(repo: str, before: str, after: str) -> LinkedChange`:
    - **completed tasks** — read the roadmap file (path from the source strategy; default `ROADMAP.md`, `.ai-factory/ROADMAP.md` if present) at `before` and at `after` (`git show <ref>:<path>` on the mirror, or equivalent); extract each version's set of done-task markers (`[x]` lines, keyed by task text/identifier); `completed_tasks` = the `after` set minus the `before` set. A relocated or reformatted line that was `[x]` in both versions is present in both sets and does not appear in the difference.
    - **commits** — `GitCommitCollector.collect(<mirror path>, "<before>..<after>")`.
- Assembled at the composition root from the injected mirror + collector.

## Files & types

- edit `src/episodic/linked_change.py` (stub → `resolve` implementation)

## Guards

- Reads the local mirror only — no network fetch.
- No roadmap at either ref, or an empty set-difference → `completed_tasks` is empty and the change falls back to commits only (never crash on a repo with no roadmap).
- Merge commits and empty ranges must not crash (as with Phase 1's collector).
- The roadmap path is taken from the source strategy, not hardcoded across the code.
- Turns 4.2.1's tests green — in particular, the relocated-already-done-line test, which a raw `+[x]`-diff approach would fail.

## Verification

- 4.2.1's red test suite passes green against this implementation, including the relocated-line non-match case.
- A push whose range flips a roadmap task from `[ ]`/absent to `[x]` → that task text appears in `completed_tasks`.
- A push that only moves or reformats an already-`[x]` task (no new completion) → that task does **not** appear in `completed_tasks`.
- A code-only push (no roadmap change) → `completed_tasks` empty, `commits` populated.
- An empty range or a merge-only range → resolves without error.
