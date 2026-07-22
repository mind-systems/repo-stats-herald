# Plan: 4.2.1 — Linked-change contract + resolve tests (red)

## Context
Define the `LinkedChange` value object and a stubbed `resolve(repo, before, after)` in `src/episodic/`, then pin the correct resolution semantics with red tests — proving a genuine become-done task is captured, a relocated already-`[x]` line is not (the false-positive trap), the roadmap path comes from the source strategy, and a no-transition/no-roadmap range falls back to commits-only without crashing. Implementation is deliberately absent (4.2.2 turns these tests green).

## Settings
- Testing: yes (red tests are this task's deliverable)
- Logging: minimal
- Docs: no

## Tasks

### Phase 1: Contract & stub

- [x] **Task 1: `LinkedChange` type + stubbed `LinkedChangeResolver`**
  Files: `src/episodic/linked_change.py` (new)
  - Add an immutable value object mirroring the codebase idiom (`@dataclass(frozen=True)`, as in `src/commits/models.py` and `src/episodic/models.py`):
    `LinkedChange` with `repo: str`, `completed_tasks: tuple[str, ...]`, `commits: CommitContext` (import `CommitContext` from `src.commits.models`).
  - Add a `LinkedChangeResolver` class with constructor DI — `__init__(self, collector: GitCommitCollector, source_strategy: SourceStrategy)` (import `GitCommitCollector` from `src.commits.collector`, `SourceStrategy` from `src.knowledge.source_strategy`). This matches spec 11's "assembled at the composition root from the injected mirror + collector" and the project's wire-concretes-only-at-the-root rule; the roadmap's shorthand `LinkedChange.resolve` maps to `LinkedChangeResolver.resolve`.
  - Method `resolve(self, repo: str, before: str, after: str) -> LinkedChange` — a STUB whose body is `raise NotImplementedError`. Include a docstring stating the intended contract (from spec 45/11):
    - `completed_tasks` = the roadmap's done-marker set at `after` minus the set at `before` (set-difference over the two full versions, NOT raw `+[x]` diff scanning).
    - **Done-marker identity key (pinned): the stable leading `N.N.N` task identifier** on each `[x]` roadmap line (e.g. the `4.2.1` in `- [x] **4.2.1 — …**`), NOT the full line text. This is the crux this task pins for 4.2.2: keying by identifier means a move, a re-indent, AND a reword of a task's description all preserve the key, so an already-`[x]` line that merely relocates appears in both the `before` and `after` sets and cancels out of the difference. `completed_tasks` holds these identifier strings. A line lacking an `N.N.N` identifier is not a keyable done-marker (out of scope for this milestone's roadmap shape).
    - roadmap path chosen via the source strategy (default `ROADMAP.md`, `.ai-factory/ROADMAP.md` if present); commits via `GitCommitCollector.collect(repo, f"{before}..{after}")`; no roadmap / no transition → empty `completed_tasks`, commits-only, never crash.
  - `src/episodic/__init__.py` already exists — no change needed.
  - No parsing/git logic here: the stub must fail only because the logic is absent, so 4.2.2 (spec 11) can green the tests.

### Phase 2: Red tests

- [x] **Task 2: Local roadmap-repo git fixture** (depends on Task 1)
  Files: `tests/episodic/conftest.py` (edit)
  - Add fixtures that build a throwaway local git repo whose history moves a roadmap between commits, following the style of `tests/github/conftest.py` (`subprocess.run(["git", ...], check=True, capture_output=True)`, pinned committer identity `user.name=herald-test` / `user.email=herald@test.invalid`, explicit `git init -b <branch>` so the fixture is independent of ambient git config). Keep these fixtures independent of the existing `pg_pool`/`store` fixtures — the resolve tests touch git only, never Postgres.
  - Provide a helper that, given an ordered list of `(roadmap_relative_path, roadmap_content)` snapshots, writes each snapshot, commits it, and returns the repo path plus the commit SHAs, so a test can pick any `before`/`after` pair. Support writing the roadmap at either `ROADMAP.md` (root) or `.ai-factory/ROADMAP.md`, and support a snapshot with no roadmap file (for the fallback case). Include a way to create a merge commit and an empty range (e.g. `before == after`) for the safety case.
  - Roadmap content in every snapshot must use real ai-factory task lines carrying a leading `N.N.N` identifier (e.g. `- [ ] **4.2.1 — Linked-change contract**`, `- [x] **4.1.1 — Episodic store contract**`), matching the pinned identity key from Task 1 — so the relocated-line test can move/reword the description while keeping the identifier stable, and `completed_tasks` assertions compare against those identifier strings.
  - Construct the resolver under test with real collaborators: `LinkedChangeResolver(GitCommitCollector(), AiFactorySourceStrategy())`.

- [x] **Task 3: Red tests pinning resolve semantics** (depends on Task 2)
  Files: `tests/episodic/test_linked_change_contract.py` (new)
  Write tests that call `resolver.resolve(repo, before, after)` and assert on the returned `LinkedChange`. Each is red against the stub (raises `NotImplementedError`) and green only once 4.2.2 implements the logic. Cover all five pinned cases from spec 45:
  - **Genuine become-done:** a task line `[ ]` (or absent) in the roadmap at `before` and `[x]` at `after` → its `N.N.N` identifier appears in `completed_tasks`.
  - **Relocated already-done (no false positive):** a task line that is `[x]` in the roadmap at BOTH `before` and `after`, but relocated within the range — moved to a different position, re-indented, AND its description reworded — while keeping its `N.N.N` identifier unchanged (so a raw `+[x]` diff would show it as an added line) → its identifier does NOT appear in `completed_tasks`. This is the adversarial planting the identifier-keyed contract from Task 1 must survive; it stays greenable by 4.2.2 precisely because identity is the stable `N.N.N` token, not the line text.
  - **Source-strategy path:** place the roadmap at `.ai-factory/ROADMAP.md` (selected by `AiFactorySourceStrategy`) with a genuine transition → captured in `completed_tasks`. This pins the root-vs-`.ai-factory` distinction (a resolver hardcoded to root `ROADMAP.md` fails it). Note: with `SourceStrategy` exposing only `selects(path) -> bool`, the test cannot prove the injected strategy *object* is consulted — that stays a 4.2.2 concern (see the deferred note below); it does catch the concrete hardcoded-root defect the spec names.
  - **Commits-only fallback:** a range with no roadmap file (or no done-transition) → `completed_tasks` is empty while `commits` (a `CommitContext`) is populated from the range; no crash.
  - **Merge / empty-range safety:** resolve over a merge-commit range and over an empty range (`before == after`) → returns without error.
  - Assert the shape too: the result is a `LinkedChange`, `completed_tasks` is a tuple of `N.N.N` identifier strings, `commits` is a `CommitContext`. Reads the local repo only — no network fetch (guaranteed by the local-git fixture, not by resolve's own I/O, since it's stubbed).

## Deferred observations

- Affects 4.2.2 (`.ai-factory/specs/11-linked-change-resolver.md`): the `SourceStrategy` ABC exposes only `selects(path) -> bool` — it cannot return or enumerate a roadmap path. So "roadmap path from the source strategy, not hardcoded" is realizable in 4.2.2 only by the resolver holding a candidate roadmap-filename list (`ROADMAP.md`, `.ai-factory/ROADMAP.md`) and existence-checking each against the tree at the ref while the strategy confirms selection. Either interpret the "not hardcoded" guard against what the interface can provide, or add a path-yielding method to `SourceStrategy`. Does not block this red-test/contract task (`resolve` is a stub).
