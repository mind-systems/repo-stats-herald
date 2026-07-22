# Code Review (Re-review) — 5.4 Episodic code-derivation

**Plan:** `.ai-factory/plans/31-5-4-episodic-code-derivation.md`
**Previous review:** `.ai-factory/reviews/31-5-4-episodic-code-derivation-review-1.md`
**Code re-read this pass:** `src/commits/collector.py`, `src/episodic/backfill.py`, `scripts/backfill_episodic.py`
**Risk:** 🟢 Low

## Per-finding verdicts (from review-1)

### Finding 1 — Non-ASCII source filenames silently skipped from distillation
**Verdict: Fixed.**
`changed_paths` now runs the diff with `-c core.quotepath=false`, so non-ASCII path bytes stay literal (UTF-8) instead of being quoted/octal-escaped — such paths then match `CodeSourceStrategy.selects` and resolve through `read_blob`. Current content (`src/commits/collector.py:82–95`):

```python
        result = subprocess.run(
            [
                self._git_bin,
                "-c",
                "core.quotepath=false",
                "-C",
                repo_path,
                "diff",
                "--name-only",
                "--no-renames",
                "--end-of-options",
                before,
                after,
            ],
```

The docstring documents the rationale (`collector.py:78–80`): "`core.quotepath=false` keeps non-ASCII path bytes literal instead of quoted/octal-escaped, so such paths still match `SourceStrategy.selects` and resolve via `read_blob`." `-c` and `-C` are both top-level git options; their relative order is irrelevant, so the invocation is correct. The downstream `read_blob(bare, after, path)` (`git show <ref>:<path>`) takes the literal pathspec unmodified, and `dest = tmp_path / path` writes it fine — the round trip holds for non-ASCII names.

### Finding 2 — Roadmap blob read up to ~4× per harnessed step
**Verdict: Not fixed — accepted as-is (was explicitly non-blocking).**
`_harness_present` still reads full roadmap content via `read_blob` (`src/episodic/backfill.py:107–117`) rather than a presence-only `git cat-file -e` probe, and `_resolve_entry → resolver.resolve` reads the roadmap versions again. This was flagged in review-1 as a minor offline-backfill inefficiency, not a defect, and requires no change to ship. No correctness impact.

## Full re-review for new issues

Re-read all three changed files in full. The logic is unchanged from review-1 except for the finding-1 fix, and all correctness confirmations from review-1 still hold:

- **Idempotency intact.** Both paths set `commit_shas` from the `before..after` range; `after ∈ before..after`, so `recorded_commit_shas` (union of stored `commit_shas`) covers every appended `after` and re-runs skip it (`backfill.py:81, 96`).
- **Mode selection mirrors the resolver.** `_harness_present` tests every `roadmap_paths()` candidate at `after` and `before`, matching `LinkedChangeResolver._read_roadmap_versions`; empty `roadmap_paths()` (code-only strategy) → `False` → distiller path.
- **`read_blob` never-raise contract holds.** Bytes captured (no `text=True`), decoded in a `try/except UnicodeDecodeError` → `None`; non-zero return → `None` (`collector.py:114–121`).
- **Temp-dir lifetime correct.** `distill` is awaited inside the `with tempfile.TemporaryDirectory()` block (`backfill.py:149–160`); files exist during distillation, cleaned per step — no worktree, no leak.
- **Path-write safety.** Materialized paths come from `git diff --name-only` (repo-relative, git-normalized — no leading `/`, no `..`) and are constrained by `CodeSourceStrategy.selects` (must start with a source root). No traversal out of the temp dir. The `core.quotepath=false` change does not weaken this — git still emits repo-relative paths, only unquoted.
- **Injection-safe.** `--end-of-options` precedes refs/paths; each ref/path is a distinct argv token.
- **Composition root.** `scripts/backfill_episodic.py` wires `CodeDistiller(OllamaClient(...))`, `CodeSourceStrategy()`, reuses `AiFactorySourceStrategy` as `source_strategy`, and passes args in the constructor's declared order; `sweep_worktrees()` added, matching `scripts/bootstrap.py`.

No new bugs, security issues, type mismatches, or missing-migration problems found. `EpisodicEntry` schema is unchanged (`completed_tasks=()` is valid). The non-code staged files (`docs/**`, `.ai-factory/**`) are out of scope.

REVIEW_PASS
