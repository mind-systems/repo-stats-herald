# Code Review — 5.4 Episodic code-derivation

**Plan:** `.ai-factory/plans/31-5-4-episodic-code-derivation.md`
**Code changed:** `src/commits/collector.py`, `src/episodic/backfill.py`, `scripts/backfill_episodic.py`
**Also read for context:** `src/episodic/models.py`, `src/episodic/store.py`, `src/episodic/linked_change.py`, `src/knowledge/code_distiller.py`, `src/knowledge/code_source_strategy.py`, `src/knowledge/source_strategy.py`, `src/github/mirror.py`, `src/llm/client.py`, `src/llm/embedder.py`
**Risk:** 🟢 Low — spec-faithful, no crash paths found; two minor edge observations below.

## Verdict

The implementation is correct and matches the reviewed plan. The critical `ctx.commits.commits` bug flagged in plan-review-1 is fixed — `_distill_entry` correctly iterates `ctx.commits` (a `CommitContext.commits` tuple) at lines 162 and 173. `read_blob` correctly captures bytes and decodes manually (no `text=True`), honoring the never-raise + return-`None` contract on invalid UTF-8. Mode selection, idempotency, the commit-message floor, and the no-worktree replay model are all preserved.

### Correctness confirmations
- **Idempotency intact.** `recorded_commit_shas` (store.py:113) returns the union of all `commit_shas`. Both entry paths set `commit_shas` from the `before..after` range, and `after ∈ before..after`, so every appended `after` is recorded and re-runs skip it (backfill.py:81, 96). `completed_tasks=()` is a valid `EpisodicEntry` value and `PgEpisodicStore.append` writes `list(())` → empty `text[]`, no schema change.
- **Harness detection mirrors the resolver.** `_harness_present` (backfill.py:107) tests every `roadmap_paths()` candidate at `after` and `before`, matching `LinkedChangeResolver._read_roadmap_versions`' present-at-either-end anchoring. A code-only strategy's empty `roadmap_paths()` → always `False` → distiller path. Root-commit `before = EMPTY_TREE_SHA` → `git show <empty-tree>:ROADMAP.md` fails → `None`, handled.
- **Root commit / deleted files.** `changed_paths(bare, EMPTY_TREE_SHA, after)` lists the full added tree (correct for a root commit); a path deleted at `after` yields `read_blob → None` and is skipped from materialization. No `git show` failure escapes.
- **Temp-dir lifetime.** `distill` is awaited inside the `with tempfile.TemporaryDirectory()` block (backfill.py:149–160), so the materialized files exist during distillation and are cleaned per step — no worktree accumulation, no leak.
- **Path-write safety.** Materialized paths come from `git diff --name-only` (repo-relative, git-normalized — no leading `/`, no `..`) and are further constrained by `CodeSourceStrategy.selects` (must start with `src/`, `lib/`, …). No traversal out of the temp dir.
- **Injection-safe git calls.** `--end-of-options` precedes refs/paths and each ref/path is a distinct argv token in the new `changed_paths` / `read_blob`.

## Non-blocking observations

**1. Non-ASCII source filenames are silently skipped from distillation (minor coverage gap).**
`git diff --name-only` quotes paths containing non-ASCII/special bytes by default (`core.quotePath=true`), e.g. `src/café.py` → `"src/caf\303\251.py"` (with literal surrounding quotes and octal escapes). Such a string fails `CodeSourceStrategy.selects` (starts with `"`, not `src/`) and would also fail `read_blob`, so the file is dropped from the distilled unit — no crash, but its behavior is omitted. If repos with non-ASCII source names are expected, add `-c core.quotepath=false` to the `changed_paths` diff invocation (`collector.py:80`). Note the pre-existing `_collect_commits` numstat path has the same quoting behavior, so this is consistent with current behavior, not a regression.

**2. Roadmap blob is read up to ~4× per harnessed step (minor inefficiency).**
On a harnessed step, `_harness_present` reads the full roadmap (up to 2 `git show`) and `_resolve_entry → resolver.resolve` reads both roadmap versions again (2 more). For an offline backfill this is acceptable; a presence-only probe (`git cat-file -e`) would avoid reading full roadmap content, but it is not worth added surface here.

Neither observation blocks the change. The two files staged alongside this task (`docs/concepts/product-scope.md`, `.ai-factory/plans/*.json`) are non-code artifacts outside this review's scope.
