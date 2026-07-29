## Plan Review Summary

**Plan:** `71-episodicbackfill-history-walk-and-derivation-mode.md` (test plan for `src/episodic/backfill.py`)
**Governing spec:** `.ai-factory/specs/73-episodic-backfill-test-plan.md` (ROADMAP_TESTS.md lines 21–22)
**Files targeted:** `tests/episodic/test_backfill.py`, `tests/episodic/test_backfill_store.py` (both new)
**Risk Level:** 🟢 Low

This is a test-only plan; no production code changes, so there are no migrations, no schema changes, and no security surface. The `EpisodicBackfill` source already correctly handles all three named hazards (per-step mode via `_harness_present(bare, before, after)`, idempotency via the `recorded` skip set, historical `changed_at` via `commit_timestamp`); the plan's job is to lock that behavior in with regression tests, and its framing of the hazards as *silent regression risks* matches the spec.

### Context Gates
- **Architecture (`.ai-factory/ARCHITECTURE.md`):** OK. Real collaborators are driven against a real fixture git repo; the only fakes (`RepoMirror`, `Embedder`, `EpisodicStore`, `LLMClient`) sit at the I/O seams the architecture designates as swappable. No feature-to-feature coupling introduced.
- **Rules (`.ai-factory/RULES.md`):** OK. File is intentionally empty (no project counter-defaults); nothing to violate.
- **Roadmap (`.ai-factory/ROADMAP_TESTS.md`):** OK. Plan links to the two `[ ]` test tasks and their shared spec `73`. Split into a git-only suite (Tasks 1–7) and a Postgres round-trip suite (Task 8) matches the roadmap's two-entry decomposition exactly.
- **Spec coverage:** OK. All 46 numbered cases in spec 73 map 1:1 onto the plan's tasks (Task1→16–17, Task2→18–24, Task3→25–31, Task4→32–37+42–44, Task5→38–41, Task6→1–5+13, Task7→6–12+14–15, Task8→45–46). No case dropped.

### Verified assumptions (all confirmed against ground truth)
- Constructor arity/order `(mirror, resolver, embedder, store, collector, canonical_refs, distiller, code_strategy, source_strategy)` — matches `backfill.py:40-60`. The "adjacent same-typed `code_strategy`/`source_strategy`" footgun the plan guards (case 22) is real.
- Fake-mirror surface `ensure` / `object_store_path` / `default_branch` — these are exactly and only the mirror members `run` + `_canonical_ref` touch. `tree()` (the sole worktree producer) is never called, so a raising fake structurally enforces "no worktree per step".
- `distiller.distill(repo, paths, tree)`, `LLMClient.generate(prompt)`, `Embedder.embed(texts)`, `EpisodicStore.append` / `recorded_commit_shas` signatures — all match.
- Resolver keys `completed_tasks` on a dotted identifier (`_TASK_ID_RE = \d+(?:\.\d+)+`); the mixed-history fixture's `- [x] 1.1` is keyable.
- `CodeSourceStrategy` requires a `src|lib|app|internal|pkg|cmd` root **and** a listed extension; the plan's "put fixture source under `src/` with a listed extension" note is correct and necessary.
- The introducing commit is artifact-mode (`_harness_present` checks `after` before `before`) → "roadmap added at commit 3 of 5" yields **2 code + 3 artifact**; the plan asserts this exact split.
- **Empirically confirmed:** `git log <EMPTY_TREE_SHA>..HEAD` and `git diff <EMPTY_TREE_SHA> HEAD` both exit 0, so the root-commit code path (`_distill_entry` with `before == EMPTY_TREE_SHA`, which runs `collect("<empty>..<after>")` under `check=True`) will not raise. Cases 1 and 44 are sound.
- `episodic_entries` schema already exists with the `(repo, changed_at)` btree the windowed query (Task 8) relies on; no migration needed.

### Critical Issues
None.

### Issues / Improvements (in-scope, non-blocking)

1. **Task 3 fixtures need a dotted task identifier, and the plan doesn't say so.** Cases "should set `completed_tasks` to only that step's `[ ]→[x]` transitions" and "should build `content` as the completed tasks followed by the range's commit messages" both require `completed_tasks` to be non-empty. The resolver only keys lines matching `\d+(?:\.\d+)+` — a fixture written as `- [x] Task one` or `- [x] 1` yields an empty set at both ends, so the transition test passes *vacuously* and the ordering test loses its subject. Spec 73's Gotchas call this out ("the resolver keys on a dotted identifier — a bare `- [x] 1` is not keyable"); the plan drops it from the Task 3 description. Add a one-line note to Task 3 (and its roadmap fixture) that done lines must carry a dotted id like `1.1`.

2. **`TMPDIR` monkeypatch (Task 4, "leave no temp directory behind") has a caching subtlety worth pinning.** `tempfile.TemporaryDirectory()` resolves its base via `tempfile.gettempdir()`, which **caches** into `tempfile.tempdir` on first use — so `monkeypatch.setenv("TMPDIR", ...)` alone may not redirect the temp dir if `tempfile` was already initialized earlier in the session. The implementer likely needs `monkeypatch.setattr(tempfile, "tempdir", str(subdir))` (or reset it to `None`) rather than relying on the env var. Non-blocking, but calling it out in the plan avoids a flaky/false-green test.

### Positive Notes
- Full spec fidelity: every one of the 46 spec cases is present and correctly grouped; nothing invented, nothing lost.
- The anti-HEAD assertion (Task 6, "invoke the LLM only for pre-roadmap steps") is the right shape — a once-at-tip evaluation would yield 0 LLM calls and fail it, which a per-repo mode decision would silently pass.
- The idempotency test correctly snapshots **three** signals (entry count, `embedder.calls`, `llm.prompts`) so a "re-derive then discard" regression can't slip through, and correctly requires the fake store's `recorded_commit_shas` to compute the real cross-entry union (the narrower in-run set vs. store read-back is exactly what idempotency must survive).
- Real-collaborator discipline (real `GitCommitCollector` / `LinkedChangeResolver` / both strategies / real `CodeDistiller` over a fake `LLMClient`) keeps the per-historical-tree contract genuinely exercised rather than stubbed; the fake `LLMClient` recording prompts keeps the bounded-units and blob-body-in-prompt guards observable.
- Correctly separates the Postgres round-trip into its own module so the git-only suite runs without a database.

## Deferred observations
- Affects: spec 73 / `tests/episodic/test_backfill.py` (Task 3) — Spec gotcha "Don't assert on `LinkedChange.repo`" (the resolver receives the bare path as its `repo` arg, so `change.repo` is a filesystem path, not the repo name; assert the entry's `repo` field, which comes from `run`'s own argument) is not restated in the plan. The plan never directs asserting on `change.repo`, so the risk is low, but an implementer building resolver-mode assertions from the plan alone could trip on it; the governing spec carries the guard.

---

The plan is architecturally sound, faithful to the governing spec (all 46 cases covered), and free of wrong API assumptions, missing migrations, or security issues. The two items under **Issues / Improvements** are in-scope plan refinements (a load-bearing fixture note and a testing-mechanics subtlety), so this review does not emit a pass token; they are small enough that a single revision pass closes both.
