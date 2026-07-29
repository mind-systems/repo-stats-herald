## Plan Review Summary

**Plan:** `71-episodicbackfill-history-walk-and-derivation-mode.md` (test plan for `src/episodic/backfill.py`)
**Governing spec:** `.ai-factory/specs/73-episodic-backfill-test-plan.md` (ROADMAP_TESTS.md lines 21–22)
**Files targeted:** `tests/episodic/test_backfill.py`, `tests/episodic/test_backfill_store.py` (both new)
**Risk Level:** 🟢 Low
**Files Reviewed:** 2 (plan + governing spec) against 9 source/fixture files

This is round 2. The three round-1 items are all folded in and verified below. This is a test-only plan — no production code, no schema/migration, no security surface. `EpisodicBackfill` already handles all three named hazards (per-step mode via `_harness_present(bare, before, after)`, idempotency via the `recorded` skip set, historical `changed_at` via `commit_timestamp`); the plan locks that behavior in with regression tests, and its hazard framing matches the spec.

### Context Gates
- **Architecture (`.ai-factory/ARCHITECTURE.md`):** OK. Real collaborators driven against a real fixture git repo; the only fakes (`RepoMirror`, `Embedder`, `EpisodicStore`, `LLMClient`) sit at the I/O seams the architecture designates as swappable. No feature-to-feature coupling introduced.
- **Rules (`.ai-factory/RULES.md`):** OK — file carries no project counter-defaults; nothing to violate.
- **Roadmap (`.ai-factory/ROADMAP_TESTS.md`):** OK. Plan links to the two `[ ]` test tasks and their shared spec 73. The git-only suite (Tasks 1–7) vs. Postgres round-trip (Task 8) split matches the roadmap's two-entry decomposition exactly.
- **Spec coverage:** OK. All 46 numbered cases map 1:1 (Task1→16–17, Task2→18–24, Task3→25–31, Task4→32–37+42–44, Task5→38–41, Task6→1–5+13, Task7→6–12+14–15, Task8→45–46). Count reconciles: 2+7+7+9+4+6+9+2 = 46. Nothing dropped, nothing invented.

### Round-1 findings — all resolved
1. **Dotted task id in Task 3 fixtures** — now stated explicitly ("done lines must carry a **dotted** task id (e.g. `- [x] 1.1 — …`) — the resolver keys `completed_tasks` on `\d+(?:\.\d+)+`"). Confirmed against `linked_change.py:16` (`_TASK_ID_RE`). Resolved.
2. **`tempfile.tempdir` caching subtlety (Task 4)** — now stated explicitly ("use `monkeypatch.setattr(tempfile, "tempdir", str(subdir))`, not `setenv("TMPDIR", ...)` alone"). Correct: `TemporaryDirectory()` resolves its base via `gettempdir()`, which caches into `tempfile.tempdir`. Resolved.
3. **Deferred round-1 observation — don't assert on `change.repo`** — now folded into Task 3's fixture notes ("Assert the entry's `repo` field … **not** `change.repo` — `_resolve_entry` passes the bare filesystem path as the resolver's `repo` arg"). Confirmed against `backfill.py:119,127`. Resolved.

### Verified assumptions (all confirmed against ground truth)
- **Constructor arity/order** `(mirror, resolver, embedder, store, collector, canonical_refs, distiller, code_strategy, source_strategy)` — matches `backfill.py:40-60` AND the real composition root `scripts/backfill_episodic.py:67-77` (which wires `code_strategy` then `strategy` last). The adjacent same-typed footgun that case 22 guards is real.
- **Collaborator signatures** — `resolver.resolve(repo, before, after)` (`linked_change.py:34`), `distiller.distill(repo, paths: list, tree: Path)` (`code_distiller.py:69`), `llm.generate(prompt)` (`code_distiller.py:100`), `embedder.embed(texts: list) -> list[list[float]]` (`embedder.py:8`), `store.append` / `recorded_commit_shas(repo) -> set` / `query(embedding, k, repo, since, until)` (`store.py`). All match.
- **`roadmap_paths()`** = `("ROADMAP.md", ".ai-factory/ROADMAP.md")` (`source_strategy.py:49`). Case 21 (`.ai-factory/ROADMAP.md` when root never existed) and case 24 (`docs/ROADMAP.md` must not flip mode — it is not a candidate path) are both sound.
- **`_harness_present`** iterates `(after, before)` per candidate, returning True if either resolves (`backfill.py:110-114`) — so cases 18 (after only) and 19 (before only) both hold, and the crossover asymmetry (`after` checked first) yields the plan's "2 code + 3 artifact" split for a roadmap introduced at commit 3 of 5.
- **`CodeSourceStrategy.selects`** requires a `src|lib|app|internal|pkg|cmd` root **and** a listed extension, and excludes dirs named `test(s)` / files matching `test_*.py` (`code_source_strategy.py:81-96`). The plan's "put fixture code under `src/` with a listed extension" note is correct and necessary; `src/bin.py` (case 37, non-UTF-8) selects and is skipped at the backfill's `read_blob` guard (`backfill.py:149-151`).
- **Root-commit code path** — `git log <EMPTY_TREE_SHA>..HEAD` re-confirmed to exit 0 empirically, so `_distill_entry`'s `collect("<empty>..<after>")` under `check=True` will not raise. Cases 1 and 44 are sound.
- **Merge-step `commit_shas`** — `_resolve_entry`/`_distill_entry` derive `commit_shas` from `collect(bare, "before..after")`; `git log base..merge` includes the merge and both side commits, while `first_parent_steps` (`--first-parent`) yields no standalone side step. Cases 13 and 28 are sound.
- **`distill` await is inside the `TemporaryDirectory` scope** (`backfill.py:146-157`) with `# {path}\n{text}` blob bodies in the prompt (`code_distiller.py:90`) — case 34's "body text appears in the prompt" assertion is well-founded.
- **Idempotency** — `run` reads `recorded_commit_shas` once and tops up with `recorded.add(after)` only (`backfill.py:70,93`); the fake store's `recorded_commit_shas` must return the cross-entry **union** (the plan requires this in the collaborator-wiring section) so case 6 tests the production-strength invariant, and `PgEpisodicStore.append` INSERTs unconditionally so store-level no-duplication (case 46) rests entirely on the skip set — exactly what the Postgres round-trip proves.
- **pytest** — `asyncio_mode = "auto"` (`pyproject.toml:22`); the existing `pg_pool` fixture lives in `tests/episodic/conftest.py:31` and truncates `episodic_entries`. The `episodic_entries` schema with the `(repo, changed_at)` btree already exists — no migration needed.

### Critical Issues
None.

### Positive Notes
- Full spec fidelity: all 46 cases present and correctly grouped; every round-1 item closed at the exact point it was raised.
- The anti-HEAD assertion (Task 6, "invoke the LLM only for pre-roadmap steps") is the right shape — a once-at-tip evaluation would yield 0 LLM calls and fail it.
- Idempotency test snapshots three signals (entry count, `embedder.calls`, `llm.prompts`) so a "re-derive then discard" regression can't slip through, and correctly requires the fake store's `recorded_commit_shas` to compute the real cross-entry union.
- Real-collaborator discipline (real `GitCommitCollector` / `LinkedChangeResolver` / both strategies / real `CodeDistiller` over a fake `LLMClient`) keeps the per-historical-tree contract genuinely exercised, with the prompt-recording fake keeping the bounded-units and blob-body guards observable.
- Postgres round-trip correctly isolated into its own module so the git-only suite runs without a database.
- Implementation note for the executor (not a plan defect, since the plan already directs adding builders to `tests/episodic/conftest.py`): the date-setting commit helper the fixtures need cannot be shared *from* `tests/commits/conftest.py` — that file is a sibling of `tests/episodic/`, and pytest conftest fixtures/helpers do not cross sibling directories (`tests/conftest.py` at the root holds only webhook fixtures). The `_commit` in `tests/episodic/conftest.py` today does **not** set the date env vars, so the executor replicates the both-dates pattern (`GIT_AUTHOR_DATE` + `GIT_COMMITTER_DATE`) into the episodic builders rather than importing it — which is what "extend … the roadmap/merge builders in `tests/episodic/conftest.py`" already asks for.

The plan is architecturally sound, faithful to the governing spec (all 46 cases), free of wrong API assumptions, and carries no missing migrations or security concerns. All round-1 findings are resolved.

PLAN_REVIEW_PASS
