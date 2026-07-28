# EpisodicBackfill — Test Plan

**Date:** 2026-07-29
**Source:** roadmap-test-coverage agent

## Source Overview

`EpisodicBackfill` (`src/episodic/backfill.py`) replays a served repo's full first-parent history against the bare mirror's object store, appending one `EpisodicEntry` per historical step with that commit's own timestamp. Per step it re-decides the derivation mode: if a roadmap candidate resolves at either end of the step it goes through `LinkedChangeResolver` (resolve + embed, no LLM); otherwise the step is distilled from its changed code blobs via `CodeDistiller`. Idempotency is a per-step skip on `after ∈ store.recorded_commit_shas(repo)`, read once at the start of `run` and topped up in memory as entries are appended.

## Instantiation

Constructor DI, nine positional args (see `scripts/backfill_episodic.py` for the real wiring order — note `code_strategy` then `source_strategy` last):

```
EpisodicBackfill(mirror, resolver, embedder, store, collector,
                 canonical_refs, distiller, code_strategy, source_strategy)
```

**Use a real temp git repo, not mocks, for the history walk.** All three central hazards live in *what git says about a historical tree*: `_harness_present` reads blobs at `before`/`after`, `_distill_entry` reads blobs at `after`, and `changed_at` comes from `git show -s --format=%cI`. A stubbed `GitCommitCollector` would make the per-historical-tree tests vacuous. Build the repo with a fixture (extend the pattern already in `tests/episodic/conftest.py` and `tests/commits/conftest.py`).

| Collaborator | Real or fake | Why |
|---|---|---|
| `GitCommitCollector` | **real** | The whole per-historical-tree contract is git behavior; stubbing it deletes the test's subject. Works against a plain `git init` repo — every method is `git -C <path>`, nothing requires an actual bare clone. |
| `LinkedChangeResolver` | **real** (`GitCommitCollector` + `AiFactorySourceStrategy`) | The `[ ]→[x]` set-difference per historical step is exactly what must be exercised. It reads the roadmap through its own `subprocess.run(["git", ...])`, not through the injected collector. |
| `AiFactorySourceStrategy` / `CodeSourceStrategy` | **real** | Pure predicates, no I/O. Faking them hides the real selection boundaries (e.g. that root-level `main.py` is *not* code-selected). |
| `RepoMirror` | **fake** | Only three members are touched: `ensure(repo, org_id)`, `object_store_path(repo) -> Path`, `default_branch(repo) -> str`. Fake should record call order (`ensure` must precede the object-store read) and should raise from any worktree-producing method so "no worktree per step" is enforced structurally. |
| `CodeDistiller` | **real, with a fake `LLMClient`** | Keeps the bounded-units guard observable: assert *prompt count per step* == number of distinct modules touched. A wholesale fake distiller would let a whole-codebase-in-one-prompt regression pass. |
| `Embedder` | **fake** | Returns `[[0.0]*768]`, records every `texts` argument. Assert `len(texts) == 1` per call and that call count equals appended-entry count. |
| `EpisodicStore` | **fake in-memory** for the behavior suite; **`PgEpisodicStore`** for a small round-trip suite | In-memory: `append` pushes to a list, `recorded_commit_shas` returns the union of every stored `commit_shas`. Postgres via the existing `pg_pool` fixture only for spec 26's `since`/`until` window verification and true no-duplicate-rows. |

## Existing Coverage

None. `grep -rn "EpisodicBackfill" tests/` is empty; `tests/episodic/` holds only `test_linked_change_contract.py` and `test_episodic_store_contract.py`. The collaborators are individually covered (`tests/knowledge/test_code_distiller_contract.py`, `tests/knowledge/test_code_source_strategy.py`, `tests/commits/test_collector.py`), so this plan targets only the orchestration and mode-selection layer that no test touches.

## Test Cases

### `run` — walk, mode selection, idempotency

1. **should append one entry per first-parent commit, including the root commit, when backfilling an N-commit repo** — `run`. The root step's `before` is `EMPTY_TREE_SHA`; an off-by-one that drops the first commit is silent.
2. **should derive early entries from code and later entries from the resolver when the repo acquires a roadmap mid-history** — `run`. The headline mixed-history case (hazard a). Fixture: commits 1–2 touch only `src/*.py`; commit 3 adds `ROADMAP.md` with a `- [x] 1.1` line; commits 4–5 flip more boxes.
3. **should invoke the LLM only for pre-roadmap steps and never for post-roadmap steps when HEAD carries a roadmap** — `run` + `_harness_present`. The explicit anti-HEAD assertion: if presence were evaluated once at the canonical tip, LLM call count would be 0 and this fails.
4. **should derive every entry from code when no commit in the whole history ever carried a roadmap** — `run`. Trajectory 1 (never harnessed).
5. **should derive every entry through the resolver with zero LLM calls when a roadmap exists at the very first commit** — `run`. Trajectory 2, and the spec-26 "no per-change LLM generation" guard: assert `fake_llm.prompts == []` across the whole history.
6. **should append nothing and issue no embed or LLM call on a second run over an unchanged repo** — `run` (hazard b). Reuse the *same* store instance across both `run` calls; snapshot entry count, `embedder.calls`, `llm.prompts` after run 1 and assert all three identical after run 2. Asserting only the entry count would let a "re-derive then discard" regression pass.
7. **should append only the entries for commits added since the last run when new commits land between runs** — `run`.
8. **should skip a step whose `after` SHA was already recorded by a live push rather than by a prior backfill** — `run`. Pre-seed the store with one entry whose `commit_shas` contains a mid-history SHA.
9. **should call `mirror.ensure` before reading the object store path** — `run`. Self-contained guard from spec 26.
10. **should never request a worktree for any historical step** — `run`. Fake mirror's worktree entry points raise. Encodes spec 26's "no full worktree per historical commit".
11. **should complete without raising and append nothing when the canonical ref does not exist in the mirror** — `run`. `first_parent_steps` returns `[]` by its no-raise contract.
12. **should append nothing for a repo with an unborn HEAD** — `run`. `git init` with zero commits.
13. **should walk only first-parent history when a side branch was merged** — `run`. Assert one entry for the merge step whose `commit_shas` includes the side-branch commits, and no standalone entry keyed on a side commit.
14. **should log `commits_walked` / `entries_appended` / `skipped` consistent with the store contents** — `run` via `caplog`. A step returning `None` must land in `skipped`, not `appended`.
15. **should embed exactly once per appended entry and never for a skipped step** — `run`.

### `_canonical_ref`

16. **should walk the configured override ref when `canonical_refs` holds an entry for the repo** — `_canonical_ref`. Non-obvious setup: give the fixture two branches with *different* commits so walking the wrong one is detectable, and make `default_branch` return the other one.
17. **should fall back to the mirror's default branch when `canonical_refs` has no entry for the repo** — `_canonical_ref`.

### `_harness_present`

18. **should return True when the roadmap exists at `after` only** — `_harness_present`. The introducing step is artifact-mode; this pins the crossover boundary, which is where the silent off-by-one lives.
19. **should return True when the roadmap exists at `before` only** — `_harness_present`. The roadmap-deleting step stays artifact-mode; documents the "lost harness" edge from `docs/concepts/derivation-modes.md`.
20. **should return False when neither end of the step has any roadmap candidate** — `_harness_present`.
21. **should return True for `.ai-factory/ROADMAP.md` when the root `ROADMAP.md` never existed** — `_harness_present`.
22. **should return False for every step when a strategy with empty `roadmap_paths()` is injected as `source_strategy`** — `_harness_present`. Pass `CodeSourceStrategy()` in the `source_strategy` slot. Pins the documented behavior and guards the argument-order footgun (`code_strategy` and `source_strategy` are adjacent and same-typed — swapping them compiles and runs silently).
23. **should return True for a roadmap file with no `[x]` lines, and still append a commits-only entry** — `_harness_present` + `_resolve_entry`. Presence, not content, selects the mode.
24. **should return False when a similarly-named non-candidate path exists** — `_harness_present`. Fixture writes `docs/ROADMAP.md`; it must not flip the mode.

### `_resolve_entry`

25. **should set `changed_at` to the historical commit's committer timestamp, not the run moment** — `_resolve_entry` (hazard c). Pin the fixture commit via **both** `GIT_AUTHOR_DATE` and `GIT_COMMITTER_DATE`; assert equality against a tz-aware datetime, and additionally assert `changed_at.year != datetime.now().year` so the intent survives a fixture rewrite.
26. **should set `completed_tasks` to only that step's `[ ]→[x]` transitions** — `_resolve_entry`. Setup: a task already `[x]` at `before` that merely relocates must not reappear.
27. **should build `content` as the completed tasks followed by the range's commit messages** — `_resolve_entry`. Assert ordering, since `content` is what gets embedded.
28. **should set `commit_shas` to every commit in the `before..after` range** — `_resolve_entry`. On a merge step that includes side-branch commits, which is what feeds later idempotency.
29. **should return `None` and skip the step when the range yields neither tasks nor message text** — `_resolve_entry`. Non-obvious setup: the only way to reach empty content is `git commit --allow-empty --allow-empty-message -m ""`.
30. **should embed the entry's content as a single-element batch** — `_resolve_entry`.
31. **should never call the distiller or the LLM in resolver mode** — `_resolve_entry`.

### `_distill_entry`

32. **should pass only the step's changed, code-selected paths to the distiller — not the whole tree** — `_distill_entry`. The backfill-side half of the bounded-units guard (spec 35).
33. **should exclude non-code paths from the distiller input** — `_distill_entry`.
34. **should write each selected blob at the `after` ref into a temp tree the distiller can actually read** — `_distill_entry`. Fake `LLMClient` asserts the file's body text appears in the prompt. Proves the `distill` await happens *inside* the `TemporaryDirectory` scope with real content.
35. **should issue one prompt per touched module rather than one prompt for the whole step** — `_distill_entry` + real `CodeDistiller.group_units`.
36. **should skip a path deleted in the step and still distill the remaining paths** — `_distill_entry`.
37. **should skip a non-UTF-8 blob and still produce an entry from the remaining paths** — `_distill_entry`. Commit a `src/bin.py` containing invalid UTF-8 bytes (write bytes directly).
38. **should fall back to the range's commit messages and issue zero LLM calls when no code path was selected** — `_distill_entry`.
39. **should fall back to the commit messages when the distiller returns only whitespace** — `_distill_entry`. The `.strip()` → `""` → `distilled or ...` fallback.
40. **should return `None` and skip when there is neither distilled text nor any commit message** — `_distill_entry`.
41. **should set `completed_tasks` to `()` and `changed_at` to the historical commit timestamp in code-derived mode** — `_distill_entry`. The hazard-(c) assertion must be made on *both* paths — a fix applied to only one is silent for half the timeline.
42. **should recreate nested directories in the temp tree for a nested source path** — `_distill_entry`.
43. **should leave no temp directory behind after a step** — `_distill_entry`. Monkeypatch `TMPDIR` to a `tmp_path` subdir and assert it's empty afterwards. Over a long history a leak is invisible per step.
44. **should treat every path as added for the root commit** — `_distill_entry`. `before == EMPTY_TREE_SHA`.

### Store round-trip (Postgres, uses the existing `pg_pool` fixture)

45. **should return only the entries inside the window when querying a backfilled repo with `since`/`until`** — `run` + `PgEpisodicStore.query`. Spec 26's stated verification; only meaningful because `changed_at` is historical, so it doubles as an end-to-end hazard-(c) check.
46. **should not create duplicate rows across two runs** — `run` + `PgEpisodicStore`. The in-memory-store idempotency test (case 6) can't catch a store-layer duplication.

## Gotchas

**The mixed-history repo fixture.** One `git init -b main` repo, committed in eras: era A writes only `src/*.py`; the transition commit adds `ROADMAP.md` (with at least one `- [x] 1.1 — …` line, since the resolver keys on a dotted identifier — a bare `- [x] 1` is not keyable); era B flips further boxes. Parameterize the crossover index so cases 2/4/5 share one builder. The transition commit itself is **artifact-mode**, because `_harness_present` checks `after` before `before` — so "roadmap added at commit 3 of 5" yields 2 code-derived and 3 artifact-derived entries, not 3 and 2. Asserting the exact split is the point; an off-by-one here mis-derives an entire era with no crash.

**Commit-date control.** `GitCommitCollector.commit_timestamp` reads `%cI` — the **committer** date. Setting only `GIT_AUTHOR_DATE` leaves the committer date at *now*, which silently reproduces hazard (c) inside the test itself. Set both env vars on every fixture commit (`tests/commits/conftest.py::_commit` already does this — reuse it). `datetime.fromisoformat` yields a **tz-aware** datetime; compare against a tz-aware expected value, never against a naive `datetime`.

**Idempotency keys.** The store's `recorded_commit_shas` is the union of `commit_shas` across *all* entries for the repo, but `run` only skips on the step's `after` SHA, and the in-run top-up is `recorded.add(after)` — it does **not** add the entry's other `commit_shas`. So the in-memory set is narrower than what a subsequent run reads back from the store. Both must produce the same skip decisions; a test that only re-runs against a fresh store misses this. Your fake store's `recorded_commit_shas` must compute the real union, or case 6 tests a weaker invariant than production.

**Coexistence along one timeline.** A repo that acquires a harness mid-history must end with code-derived entries and artifact-anchored entries in the *same* log, ordered by `changed_at`. Assert on the entry list sorted by `changed_at` and check the mode flips exactly once, at the transition commit — not that "some entries are of each kind", which a per-repo (rather than per-step) mode decision would also satisfy about half the time.

**Code selection is narrower than it looks.** `CodeSourceStrategy` requires the path to start with `src/`, `lib/`, `app/`, `internal/`, `pkg/`, `cmd/` **and** carry a listed extension. A fixture that commits `main.py` at the repo root selects nothing, no LLM call fires, and the entry silently falls back to commit messages — a distillation test that "passes" while never distilling. Always put fixture code under `src/`.

**Fake-mirror surface.** Only `ensure`, `object_store_path`, `default_branch` are used. `object_store_path` should return the fixture's `tmp_path/repo` — a plain non-bare repo is fine, since `GitCommitCollector` and `LinkedChangeResolver` both shell out with `git -C`. Note `LinkedChangeResolver._read_roadmap_at` hardcodes the `"git"` binary rather than going through the collector's `git_bin`, so a `git_bin` injection would not apply to it.

**Don't assert on `LinkedChange.repo`.** `_resolve_entry` passes the *bare path* as the resolver's `repo` argument, so `change.repo` is a filesystem path, not the repo name. The entry's `repo` field comes from `run`'s own argument and is the one to assert on.

**pytest config.** `asyncio_mode = "auto"` — async tests need no marker. The Postgres cases require a live database; keep them in a separate module from the git-only behavior suite so the latter runs without Postgres.
