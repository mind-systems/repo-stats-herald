## Plan Review — 5.4 Episodic code-derivation

**Plan:** `.ai-factory/plans/31-5-4-episodic-code-derivation.md`
**Files reviewed:** plan + spec `35-episodic-code-derivation.md`, `docs/concepts/derivation-modes.md`, and all touched/depended code (`src/episodic/backfill.py`, `src/commits/collector.py`, `src/commits/models.py`, `src/episodic/linked_change.py`, `src/episodic/models.py`, `src/knowledge/code_distiller.py`, `src/knowledge/code_source_strategy.py`, `src/knowledge/source_strategy.py`, `src/llm/embedder.py`, `src/llm/client.py`, `src/github/mirror.py`, `scripts/backfill_episodic.py`, `scripts/bootstrap.py`)
**Risk Level:** 🟡 Medium

### Context Gates
- **Spec alignment:** PASS. The per-step mode selection (roadmap present → resolver; absent → distiller) faithfully implements spec §Change and matches `derivation-modes.md`'s "profile evaluated per historical tree." Keying on roadmap presence at `after` **or** `before` correctly mirrors `LinkedChangeResolver._read_roadmap_versions`, so the harness-detection boundary agrees with the resolver's own anchoring behavior. Poor-harness (docs but no roadmap) repos correctly route to code-derivation, consistent with the concept doc's spectrum.
- **Architecture (`ARCHITECTURE.md` / `CLAUDE.md`):** PASS. Moving the new git reads onto `GitCommitCollector` (rather than inline in the backfill) honors "git-command details live in `GitCommitCollector`." The DEVIATION annotation is warranted and correctly flagged. DI-of-abstractions and composition-root-only wiring are preserved.
- **Referenced files/APIs:** Verified present and signatures consistent — `CodeDistiller.distill(repo, paths, tree)`, `EpisodicEntry` fields, `Embedder.embed`, `OllamaClient(url, model, api_key)`, `CodeSourceStrategy.selects`, `AiFactorySourceStrategy.roadmap_paths()`, `mirror.sweep_worktrees()`, `mirror.object_store_path()`. `docs/concepts/derivation-modes.md` exists. No DB migration required (`EpisodicEntry` schema unchanged; `completed_tasks=()` is valid).
- **Roadmap linkage:** PASS — task 5.4 is a `feat` extending 4.4, spec references present.

### Critical Issues

**1. `ctx.commits.commits` in Task 4 raises `AttributeError` (plan lines 55 & 58).**
Task 4 does `ctx = self._collector.collect(bare, f"{before}..{after}")`. `GitCommitCollector.collect` returns a **`CommitContext`** (collector.py:32–35), whose `.commits` field is *already* the `tuple[Commit, ...]`. The plan then writes:
- line 55: `"\n".join(c.message for c in ctx.commits.commits)`
- line 58: `commit_shas=tuple(c.sha for c in ctx.commits.commits)`

`ctx.commits` is the tuple, so `ctx.commits.commits` accesses `tuple.commits` → `AttributeError` at runtime, on the very first pre-harness step. The double `.commits.commits` was copied from the resolver path (`change.commits.commits`), which is correct only because there `change` is a `LinkedChange` and `change.commits` is a `CommitContext`. In `_distill_entry` the variable is a `CommitContext`, not a `LinkedChange`. Both occurrences must be `ctx.commits`. With `Testing: no`, no test will catch this before it ships.

### Non-blocking findings

**2. `read_blob` UTF-8 guard is unimplementable with the `text=True` pattern the plan points at (Task 1).**
Task 1 requires `read_blob` to return `None` when "the content is not valid UTF-8" and to be never-raising ("mirror the existing `first_parent_steps` no-raise contract"), while also saying "Reuse the `check=False` + `returncode` pattern already in this file." The existing patterns in `collector.py` use `subprocess.run(..., text=True)`. With `text=True`, decoding happens *inside* `subprocess.run`, so an invalid-UTF-8 blob raises `UnicodeDecodeError` there — before any caller guard can convert it to `None`, breaking the stated never-raise + return-`None` contract. The instruction "guard decode" implies the correct approach (capture bytes with `capture_output=True` and no `text=True`, then `stdout.decode("utf-8")` inside `try/except UnicodeDecodeError`), but the "reuse the pattern" wording invites a naive copy that violates the contract. Pin this explicitly in Task 1 so the implementer captures bytes and decodes manually.

### Positive Notes
- The "read blobs by SHA into a scratch temp dir, never `mirror.tree`" design correctly preserves the backfill's deliberate no-worktree replay model and avoids the deferred-reclamation disk-leak of `RepoMirror.tree`; per-step `TemporaryDirectory` cleanup is sound.
- Idempotency skip, `walked/appended/skipped` counters, empty-content-→-skip semantics, and the commit-message floor are all explicitly preserved, keeping the code path byte-compatible with 4.4's resolver path where it should be.
- `--no-renames --end-of-options` and passing refs/paths as separate argv elements keep the new git reads injection-safe.
- Constructor parameter order in Task 2 and the call site in Task 5 agree; script wiring mirrors `scripts/bootstrap.py` correctly, including `sweep_worktrees()`.

### Minor observations (address alongside the fix, no re-review needed)
- Task 4's tail phrase "embedded and appended identically to the resolver path **by the caller**" is loose: Task 4 itself computes the embedding inside `_distill_entry` and returns a fully-built `EpisodicEntry`. Intent (caller only appends) is clear, but the wording could mislead into a double-embed; keep embedding inside each helper, caller appends only.
- Task 3 does not restate that `_resolve_entry` must be `async` (it awaits `embed`); trivially implied but worth being explicit given the extraction.
- Task 1's "On non-zero return (e.g. merge/unknown ref) return `()`" for `changed_paths`: a two-tree `git diff <before> <after>` does not fail on merge commits (it is a plain two-tree diff), so the merge rationale is misworded — harmless, the `()`-on-nonzero contract is still correct for unknown refs.

Fix finding 1 (a real runtime error) and pin finding 2; the plan is otherwise architecturally sound and spec-faithful.
