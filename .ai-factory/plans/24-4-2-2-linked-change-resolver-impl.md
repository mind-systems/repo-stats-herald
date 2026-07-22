# Plan: 4.2.2 — Linked-change resolver (impl)

## Context
Implement `LinkedChangeResolver.resolve` so it derives a push's completed roadmap tasks by set-difference of done-markers between the roadmap at `before` and at `after` (robust to moved/reformatted lines) plus the range's commits — greening 4.2.1's six red tests in `tests/episodic/test_linked_change_contract.py`.

## Settings
- Testing: no
- Logging: minimal
- Docs: no

## Ground truth already verified
- The stub and its contract docstring live in `src/episodic/linked_change.py` (`LinkedChange`, `LinkedChangeResolver.__init__(collector, source_strategy)`, `resolve(repo, before, after)` raising `NotImplementedError`). Keying is by the leading `N.N.N` task identifier, NOT the full line text.
- Red tests in `tests/episodic/test_linked_change_contract.py` pin: genuine become-done capture, relocated-already-done non-match (`completed_tasks == ()`), source-strategy path (`.ai-factory/ROADMAP.md`-only tree), commits-only fallback with no roadmap, and merge/empty-range safety. Fixtures in `tests/episodic/conftest.py` construct `resolver = LinkedChangeResolver(GitCommitCollector(), AiFactorySourceStrategy())` and build throwaway local git repos.
- `GitCommitCollector.collect(repo_path, rev_range)` (`src/commits/collector.py`) already tolerates empty ranges and merge commits (read-only `git log`). Reuse it verbatim; do not add new commit-reading logic.
- `AiFactorySourceStrategy` (`src/knowledge/source_strategy.py`) knows the artifact layout, including `ROADMAP.md` / `.ai-factory/ROADMAP.md` in `_ROOT_OR_AI_FACTORY`, but exposes only `selects(path)` today.

## Tasks

### Phase 1: Roadmap-path source

- [x] **Task 1: Expose roadmap candidate paths on the source strategy**
  Files: `src/knowledge/source_strategy.py`
  Give the strategy seam ownership of *which* files are roadmaps, so the resolver never hardcodes the name (spec guard: "roadmap path is taken from the source strategy, not hardcoded across the code").
  - On the `SourceStrategy` ABC add a concrete (non-abstract) method `roadmap_paths(self) -> tuple[str, ...]` returning `()` by default — a profile with no roadmap (e.g. 5.1's future `CodeSourceStrategy`) then falls back to commits-only for free.
  - Override it in `AiFactorySourceStrategy` to return the candidate roadmap-relative paths in priority order. `roadmap_paths` is the single home for the *ordered roadmap candidate list*; write the explicit literal tuple there: `("ROADMAP.md", ".ai-factory/ROADMAP.md")`. Do NOT try to derive it from `_ROOT_OR_AI_FACTORY` — that set is unordered and also holds the `ARCHITECTURE.md` entries, so it cannot yield an ordered roadmap-only tuple by a plain reference. (`_ROOT_OR_AI_FACTORY` remains the home for the `selects` membership check; the two serve different questions and are allowed to name the roadmap files independently.)
  - Do not touch `selects` behavior; existing `tests/knowledge/test_source_strategy.py` must stay green (it only asserts `selects`).

### Phase 2: Resolver implementation

- [x] **Task 2: Implement done-marker extraction** (depends on Task 1)
  Files: `src/episodic/linked_change.py`
  Add a private pure helper on `LinkedChangeResolver` (e.g. `_done_identifiers(content: str) -> set[str]`):
  - For each line, match a done checkbox: leading optional whitespace, a `-`/`*` bullet, then `[x]` (case-insensitive, e.g. `\[[xX]\]`). A `[ ]` (space) line is NOT done.
  - From a matched done line, extract the first dotted task identifier via `\d+(?:\.\d+)+` (matches the tests' three-part `4.2.1`/`4.1.1` and real two-part IDs like `2.2`; a bare phase number like `4` is intentionally not a keyable marker, per the stub docstring). A done line with no such identifier is skipped.
  - Return the set of identifiers. Keep this helper pure (string in → set out), no I/O — it is the piece that makes a relocated/re-indented/reworded already-`[x]` line cancel out (same identifier in both `before` and `after` sets).

- [x] **Task 3: Implement roadmap reading at a ref** (depends on Task 1)
  Files: `src/episodic/linked_change.py`
  Add a private helper (e.g. `_read_roadmap_at(repo: str, ref: str, path: str) -> str | None`) that runs `git -C <repo> show --end-of-options <ref>:<path>` (the spec explicitly endorses `git show <ref>:<path>` on the mirror). This resolver owns its own git-read detail, mirroring how `GitCommitCollector` owns its commit-read detail.
  - Pass `--end-of-options` before the `<ref>:<path>` positional and use list-form `subprocess.run([...])` (never `shell=True`), matching the argument hygiene `GitCommitCollector` already applies to these same webhook-sourced refs (`src/commits/collector.py:49`) — a `before`/`after` ref beginning with `-` must not be parsed as an option.
  - Use `subprocess.run(..., capture_output=True, text=True, check=False)`; on a non-zero return code (path absent at that ref, i.e. no roadmap) return `None` — never raise. This is the "no roadmap → never crash" guard.
  - Local plumbing only: `git show` performs no network I/O. Do NOT call `git fetch`/`git pull` anywhere — reads the mirror only.

- [x] **Task 4: Implement `resolve` orchestration** (depends on Tasks 2, 3)
  Files: `src/episodic/linked_change.py`
  Replace the `raise NotImplementedError` body with:
  - **Roadmap path selection:** iterate `self._source_strategy.roadmap_paths()`; for each candidate read it at both `after` and `before` (Task 3). Pick the first candidate present at *either* ref. If no candidate is present at either ref → treat both roadmap versions as empty (commits-only fallback).
  - **completed tasks:** `before_set = _done_identifiers(before_content or "")`, `after_set = _done_identifiers(after_content or "")`; completed identifiers = those in `after_set` but not `before_set`. Emit them as a tuple in deterministic order — iterate the `after` document's done lines in order and include each fresh identifier once (stable, dedup) — so a relocated already-done line and the empty-difference case both yield `()`.
  - **commits:** `self._collector.collect(repo, f"{before}..{after}")`; assign to `LinkedChange.commits`. For `before == after` this is an empty range (no commits) and must not crash — the collector already handles it.
  - Return `LinkedChange(repo=repo, completed_tasks=<tuple>, commits=<context>)`.
  - Keep the module-level regexes as compiled constants (following `collector.py`'s style). Remove the stub's "this is a stub" docstring wording; keep an accurate present-tense description of the implemented behavior (no plan/roadmap references in comments).

## Verification (run existing suite, do not author new tests)
- `make eval` is unrelated here; instead run `uv run pytest tests/episodic/test_linked_change_contract.py` — all five cases pass: genuine become-done captures `4.2.1`; relocated already-done `4.1.1` gives `completed_tasks == ()`; `.ai-factory/ROADMAP.md`-only tree still finds `4.2.1`; no-roadmap tree yields empty tasks with populated commits; merge and empty ranges resolve without error.
- Re-run `uv run pytest tests/knowledge/test_source_strategy.py` to confirm the `roadmap_paths` addition did not disturb `selects`.
