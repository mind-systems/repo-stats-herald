## Code Review Summary

**Artifact reviewed:** `.ai-factory/plans/24-4-2-2-linked-change-resolver-impl.md` (plan for task 4.2.2 — Linked-change resolver impl)
**Files the plan touches:** `src/knowledge/source_strategy.py`, `src/episodic/linked_change.py`
**Risk Level:** 🟢 Low

Re-reviewed against the full reference chain: the stub (`src/episodic/linked_change.py`), the source strategy (`src/knowledge/source_strategy.py`), the collector (`src/commits/collector.py`), the six red tests (`tests/episodic/test_linked_change_contract.py`), the fixtures (`tests/episodic/conftest.py`), the source-strategy test policy (`tests/knowledge/test_source_strategy.py` asserts `selects` only), and both governing specs (`11-linked-change-resolver.md` line 51 of `ROADMAP.md`, and `45-linked-change-contract.md`). Verified the two non-blocking issues raised in plan-review-1 are both resolved in this revision.

### Resolution of plan-review-1 findings
1. **`--end-of-options` guard on `git show` — RESOLVED.** Task 3 now specifies `git -C <repo> show --end-of-options <ref>:<path>` in list-form `subprocess.run([...])` (line 39–40), matching the argument hygiene `GitCommitCollector` applies at `src/commits/collector.py:49` to these same webhook-sourced refs. I confirmed on git 2.50.1 that `git show --end-of-options <sha>:<path>` returns the blob (exit 0) and that a missing path exits non-zero (128) — so the `check=False` → return `None` guard in Task 3 fires exactly on the "no roadmap at that ref" case.
2. **`_ROOT_OR_AI_FACTORY` reuse conflict — RESOLVED.** Task 1 (line 25) now tells the implementer to write the explicit ordered literal `("ROADMAP.md", ".ai-factory/ROADMAP.md")` in `roadmap_paths` and *not* to derive it from the unordered `_ROOT_OR_AI_FACTORY` set (which also holds the `ARCHITECTURE.md` entries). The single-home rationale — `roadmap_paths` owns the ordered candidate list, `_ROOT_OR_AI_FACTORY` owns the `selects` membership check — is stated. The contradiction is gone.

### Algorithm trace (all six tests green)
- **genuine:** before `{4.1.1}` → after `{4.1.1, 4.2.1}` ⇒ `("4.2.1",)`, `4.1.1` absent. ✓
- **relocated:** the moved/re-indented/reworded `[x] 4.1.1` is `{4.1.1}` in both sets ⇒ `()` — the false-positive trap is defeated by keying on the `\d+(?:\.\d+)+` identifier, not line text. ✓
- **ai-factory path:** root `ROADMAP.md` absent at both refs → skipped; `.ai-factory/ROADMAP.md` present → chosen ⇒ `4.2.1` captured (candidate priority order matters here and is preserved). ✓
- **no-roadmap:** both candidates absent at both refs → both versions empty ⇒ `()`; range `shas[0]..shas[1]` carries one `src_marker.txt` commit ⇒ commits populated. ✓
- **merge / empty-range:** no roadmap files → `()`; `collect` tolerates both the merge range and the `sha..sha` empty range verbatim. ✓

### Context Gates
- **Architecture (`.ai-factory/ARCHITECTURE.md` + project CLAUDE.md):** PASS. The git-read detail stays encapsulated inside `LinkedChangeResolver` (mirrors "owned details stay inside the owning class"; the collector owns commit-reads, this resolver owns its `git show` read). `episodic` depends on `knowledge`'s public `SourceStrategy` ABC injected via constructor — allowed by rule 42 ("depend on A's public class/interface, injected via constructor"), and pre-existing in the stub. No feature-internal import introduced. Concretes stay wired at the conftest/composition root. No WARN.
- **Rules (`.ai-factory/RULES.md`):** PASS. File intentionally empty (no counter-defaults); nothing to violate.
- **Roadmap linkage:** PASS. `ROADMAP.md` line 51 (`4.2.2`) names `Spec: .ai-factory/specs/11-linked-change-resolver.md`; the plan heading `# Plan: 4.2.2 — Linked-change resolver (impl)` matches, and the set-difference behavior + guards conform to that spec.
- **Skill-context (`aif-review/SKILL.md`):** absent — no project-specific overrides to apply.
- **Test policy:** PASS. Plan authors no new tests and greens the existing red suite — correct for a fail-silently surface already pinned by 4.2.1.

### Critical Issues
None. The plan is implementable exactly as written and turns the full suite green.

### Positive Notes
- Keying done-markers by the leading `\d+(?:\.\d+)+` identifier (Task 2) is the precise mechanism that cancels a relocated already-`[x]` line out of the difference; the plan ties it to the adversarial test and correctly excludes bare phase numbers like `4`.
- The `roadmap_paths(self) -> ()` default on the ABC (Task 1) is a clean forward-looking seam: 5.1's future `CodeSourceStrategy` inherits commits-only fallback for free, and `selects` is untouched so `tests/knowledge/test_source_strategy.py` stays green.
- Reusing `GitCommitCollector.collect(repo, f"{before}..{after}")` verbatim (Task 4) inherits the empty-range/merge tolerance and the `--end-of-options` guard rather than reimplementing commit-reading — matches the "do not add new commit-reading logic" ground-truth note.
- `_read_roadmap_at` returning `None` on non-zero exit with `check=False`, folded with `before_content or ""` in Task 4, is the correct "no roadmap → never crash" shape; deterministic dedup by re-scanning the `after` document's done lines gives a stable `completed_tasks` order.

## Deferred observations
- Affects: future consumers / spec `11-linked-change-resolver.md` — Task 4's path rule "pick the first candidate present at *either* ref" reads both `before` and `after` from a **single** chosen path. If a roadmap is *moved across paths within one range* (root `ROADMAP.md` at `before` → `.ai-factory/ROADMAP.md` at `after`), the resolver picks root `ROADMAP.md` (present at `before`), reads `after` there as absent → empty, and would miss real completions in that push. This is outside 4.2.2's contract — the spec frames the path as an either/or ("default `ROADMAP.md`, `.ai-factory/ROADMAP.md` if present") and no test exercises a mid-range relocation — so it is correctly out of scope here; noting it for whoever later hardens live-push resolution.

PLAN_REVIEW_PASS
