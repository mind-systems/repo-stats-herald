## Code Review Summary

**Artifact reviewed:** `.ai-factory/plans/24-4-2-2-linked-change-resolver-impl.md` (plan for task 4.2.2 — Linked-change resolver impl)
**Files the plan touches:** `src/knowledge/source_strategy.py`, `src/episodic/linked_change.py`
**Risk Level:** 🟢 Low

Verified the plan against its reference chain: the stub (`src/episodic/linked_change.py`), the source strategy (`src/knowledge/source_strategy.py`), the collector (`src/commits/collector.py`), the six red tests (`tests/episodic/test_linked_change_contract.py` — the plan says "five" but there are six functions: genuine, relocated, ai-factory-path, no-roadmap, merge, empty-range), the fixtures (`tests/episodic/conftest.py`), the source-strategy test (`tests/knowledge/test_source_strategy.py`), and both governing specs (`11-linked-change-resolver.md`, `45-linked-change-contract.md`).

The set-difference algorithm the plan specifies greens every one of the six tests. I traced each case by hand:
- **genuine:** before `{4.1.1}` → after `{4.1.1, 4.2.1}` ⇒ `("4.2.1",)`; `4.1.1` absent. ✓
- **relocated:** the moved/re-indented/reworded `4.1.1 [x]` is `{4.1.1}` in both sets ⇒ `()`. ✓ (the adversarial false-positive trap is correctly defeated by keying on the `N.N.N` identifier, not line text)
- **ai-factory path:** root `ROADMAP.md` absent at both refs → skipped; `.ai-factory/ROADMAP.md` present → chosen ⇒ `4.2.1` captured. ✓
- **no-roadmap:** both candidates absent at both refs → both versions empty ⇒ `()`, commits populated (one commit in `before..after`). ✓
- **merge / empty-range:** no roadmap files → `()`; collector tolerates both ranges. ✓

### Context Gates
- **Architecture (`.ai-factory/ARCHITECTURE.md` / project CLAUDE.md):** PASS. The plan keeps the git-read detail inside `LinkedChangeResolver` (mirroring "owned details stay inside the owning class" — `GitCommitCollector` owns commit-reads, this resolver owns its `git show` read). No feature→feature import is introduced; `linked_change.py` depends only on `commits/` and `knowledge/` abstractions, as today. Concretes stay wired at the conftest/composition root. WARN-free.
- **Rules (`.ai-factory/RULES.md`):** PASS. The file is intentionally empty (no project counter-defaults); nothing to violate.
- **Roadmap linkage:** PASS. Task line 51 of `ROADMAP.md` (`4.2.2`) names `Spec: .ai-factory/specs/11-linked-change-resolver.md`; the plan's `# Plan: 4.2.2 — Linked-change resolver (impl)` heading matches, and its behavior conforms to that spec's set-difference contract and guards.
- **Test policy:** PASS. Plan authors no new tests and only greens the existing red suite — correct for a fail-silently surface already pinned by 4.2.1.

### Critical Issues
None. The plan is implementable as written and turns the suite green.

### Issues to address (non-blocking, in-scope)

1. **`git show` drops the `--end-of-options` guard that the rest of the codebase applies to `before`/`after` (Task 3).** `GitCommitCollector` deliberately passes `--end-of-options` before the `rev_range` built from these same webhook-sourced refs (`src/commits/collector.py:49`), and `mirror.py` applies git-argument hygiene on the untrusted paths it handles. Task 3's new `git show <ref>:<path>` invocation passes `before`/`after` with no such guard. Because the argument is the combined form `f"{ref}:{path}"`, a ref beginning with `-` would make the whole positional look like an option to `git show`. Practical risk is low (GitHub delivers 40-char hex SHAs, and the tests use `rev-parse` output), but the omission is an inconsistency with the project's own established guard for exactly these values. Recommend Task 3 specify `git -C <repo> show --end-of-options <ref>:<path>` (and, as the plan already implies, list-form `subprocess.run([...])`, never `shell=True`).

2. **Task 1's "reuse `_ROOT_OR_AI_FACTORY`" instruction conflicts with the ordered literal it also mandates.** The plan tells the implementer to return the priority-ordered tuple `("ROADMAP.md", ".ai-factory/ROADMAP.md")` *and* to "reuse/reference the existing `_ROOT_OR_AI_FACTORY` knowledge rather than introducing a second literal home … (single source of truth)." `_ROOT_OR_AI_FACTORY` is an unordered `set` that also contains the two `ARCHITECTURE.md` entries, so it cannot yield an ordered roadmap-only tuple by a plain reference — satisfying both instructions cleanly is not possible, and the two most likely resolutions (write the literal tuple anyway, or filter+sort the set) each pick one instruction over the other. Recommend the plan pick one: either accept the explicit literal as the single home (drop the reuse clause), or derive the tuple deterministically from a shared constant. This is a clarity gap, not a correctness bug — either resolution still greens the tests.

### Positive Notes
- Keying done-markers by the leading `N.N.N` identifier (Task 2) is the exact mechanism that cancels a relocated already-`[x]` line out of the set-difference — the plan correctly identifies this as the crux and ties it to the adversarial test.
- The `roadmap_paths() -> ()` default on the ABC (Task 1) is a clean, forward-looking seam: 5.1's future `CodeSourceStrategy` inherits commits-only fallback for free without a special case, and `selects` is left untouched so `tests/knowledge/test_source_strategy.py` stays green (verified — that suite asserts `selects` only).
- Reusing `GitCommitCollector.collect(repo, f"{before}..{after}")` verbatim (Task 4) inherits its empty-range/merge tolerance and its `--end-of-options` guard rather than reimplementing commit-reading — matches the "do not add new commit-reading logic" ground-truth note.
- `_read_roadmap_at` returning `None` on non-zero exit with `check=False` (Task 3) is the right "no roadmap → never crash" shape, and `before_content or ""` (Task 4) folds `None` and empty content into one path.
- The plan correctly reads the fixture reality: the `resolver` fixture needs no Postgres, so the suite runs on git alone.

## Deferred observations
- Affects: future consumers / spec `11-linked-change-resolver.md` — The path-selection rule "pick the first candidate present at *either* ref" reads `before` and `after` from a **single** chosen path. If a roadmap is *moved across paths within one range* (e.g. root `ROADMAP.md` at `before` → `.ai-factory/ROADMAP.md` at `after`), the resolver picks root `ROADMAP.md` (present at `before`), reads `after` there as absent → empty, and would miss real completions in that push. This is outside 4.2.2's contract — the spec frames the path as "default `ROADMAP.md`, `.ai-factory/ROADMAP.md` if present," an either/or, and no test exercises a mid-range relocation — so it is correctly out of scope here; noting it for whoever later hardens live-push resolution.
