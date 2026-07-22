## Plan Review Summary

**Plan:** 5.4 — Episodic code-derivation (`.ai-factory/plans/31-5-4-episodic-code-derivation.md`)
**Files Reviewed:** plan + 11 grounding files (backfill, collector, distiller, resolver, source strategies, mirror, embedder, models, both scripts, spec, concept)
**Risk Level:** 🟢 Low

### Context Gates
- **Architecture** (`.ai-factory/ARCHITECTURE.md`) — PASS. The plan honors the load-bearing principles: git-command details stay inside `GitCommitCollector` (Task 1), features receive abstractions via constructor DI (`distiller`/`code_strategy`/`source_strategy` in Task 2), and concretes are wired only at the composition root (`scripts/backfill_episodic.py`, Task 5). The deliberate widening of the spec's terse "edit `backfill.py`" file list to add collector methods is correctly justified and flagged as a `DEVIATION` — this is conformance to the architecture principle, not a deviation from intent.
- **Rules** (`.ai-factory/RULES.md`) — PASS. File is intentionally empty (no project counter-defaults); nothing to enforce.
- **Roadmap** (`.ai-factory/ROADMAP.md`) — PASS. Task linked to line `5.4` → `Spec: .ai-factory/specs/35-episodic-code-derivation.md` (read). The roadmap line's older `distill(repo, paths)` two-arg signature (from 5.2.1's contract) is superseded by the built code's `distill(repo, paths, tree)`; the plan correctly follows ground truth (Task 4 passes `Path(tmp)` as the third arg), not the stale contract line.
- **Skill-context** — none present (`.ai-factory/skill-context/aif-review/SKILL.md` absent); no project overrides to apply.

### Critical Issues
None.

### Verification against ground truth

Every non-trivial assumption in the plan was checked against the code and holds:

- **`read_blob` bytes/manual-decode reasoning (Task 1)** is correct and important. The existing resolver's `_read_roadmap_at` uses `text=True` because a roadmap is UTF-8; for arbitrary blobs `text=True` would raise `UnicodeDecodeError` *inside* `subprocess.run` before any guard, breaking the never-raise contract. Capturing bytes + `try/except UnicodeDecodeError` is the right primitive, and mirrors `CodeDistiller.distill`'s own per-file UTF-8 skip.
- **`--end-of-options` on `git diff`/`git show`** is an established pattern in this repo (`first_parent_steps`, `commit_timestamp`, resolver), so both new commands compose safely.
- **Two-tree diff on merge commits / root commit** — `git diff <before> <after>` never fails on a merge (unlike a range), and `before == EMPTY_TREE_SHA` for the root step lists all files, consistent with the collector's documented empty-tree convention. `--no-renames` correctly prevents rename arrows from corrupting `--name-only` paths.
- **Harness keyed on roadmap presence** matches the resolver exactly: `_harness_present` probing `source_strategy.roadmap_paths()` at `after`/`before` is the same present-at-either-ref test as `LinkedChangeResolver._read_roadmap_versions`. Empty `roadmap_paths()` (a code-only strategy) → always code path, matching `docs/concepts/derivation-modes.md`'s "poor/no harness → distill from code." The crossover commit (introduces roadmap: absent@before, present@after) correctly routes to the resolver, whose set-difference then yields the full done-set — the intended binary crossover the spec sanctions.
- **`ctx.commits` vs `.commits.commits`** — the plan's explicit note is correct: `collect()` returns a `CommitContext` whose `.commits` is already `tuple[Commit, ...]`, whereas the resolver path's variable is a `LinkedChange` whose `.commits` is a `CommitContext`. Both branches build `commit_shas`/content correctly.
- **No-worktree / read-by-SHA constraint** is preserved: the code path materializes selected blobs into a `tempfile.TemporaryDirectory()` scratch dir per step (auto-cleaned), never `mirror.tree()` — honoring `RepoMirror.tree`'s deferred-reclamation-leak warning. `run()` already calls `mirror.ensure`, so `object_store_path` is populated.
- **Path safety of the scratch write** — changed paths are filtered through `CodeSourceStrategy.selects`, which requires a `src/`|`lib/`|… prefix and a source extension, so no absolute or `..` paths reach the `<tmp>/<path>` write; creating parents is called out.
- **Embedding discipline** — each helper embeds and returns `EpisodicEntry | None`; the loop only appends and updates `recorded`/counters. This preserves today's "helper embeds, caller appends, never double-embed" shape and the empty-content skip. `EpisodicEntry(completed_tasks=(), …)` matches the frozen dataclass (`recorded_at` defaulted).
- **Constructor order ↔ wiring** — Task 2's param order (`… canonical_refs, distiller, code_strategy, source_strategy`) matches Task 5's positional call `EpisodicBackfill(…, settings.canonical_refs, distiller, code_strategy, strategy)`. Script imports (`OllamaClient`, `CodeDistiller`, `CodeSourceStrategy`) and the `CodeDistiller(OllamaClient(...))` construction mirror `scripts/bootstrap.py` exactly. Reusing the single `AiFactorySourceStrategy()` for both the resolver and `source_strategy` is correct (only `roadmap_paths()` is used).
- **`sweep_worktrees()` in the script** is harmless (the backfill opens no worktrees) and consistent with `bootstrap.py`'s startup hygiene; justified in-plan.
- **`Path`/`tempfile` imports** — correctly called out as new to `backfill.py`.

### Positive Notes
- Exceptionally well-grounded: the plan pre-empts the exact traps an implementer would hit (the `text=True` decode trap, the double-`.commits`, the worktree-leak, the merge-safe two-tree diff) with cited reasons rather than bare instructions.
- Scope discipline is clean — the live push writer (4.3) is explicitly excluded, and the collector-vs-orchestration split is spelled out with the `DEVIATION` annotation the diff should carry.
- Graceful degradation is preserved end-to-end: a step with no selected source changes (or empty distilled text) falls back to the commit-message floor, so the "skip only when everything is empty" invariant and idempotency both survive the split.

The plan is implementable as written and produces correct, architecture-conformant code.

PLAN_REVIEW_PASS
