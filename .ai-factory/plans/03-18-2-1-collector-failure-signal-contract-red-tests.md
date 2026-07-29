# Plan: 18.2.1 — Collector failure-signal contract (red tests)

## Context
Declare — but do not yet wire — a distinct failure signal so `GitCommitCollector.new_commits` can one day tell a genuine empty range apart from a non-zero `git` exit, and pin that contract with red tests that fail against today's silently-empty body.

## Settings
- Testing: yes (this task's deliverable is tests plus a type declaration)
- Logging: none
- Docs: no

## Decision: the failure-signal shape (the fork)

The spec leaves the shape open — a dedicated exception type vs. a sentinel return vs. an optional-wrapped result — with no obviously-correct default. Settled here as **a dedicated exception type**, `CommitCollectionError`, defined in `src/commits/collector.py`.

Rationale:
- The eventual consumer behavior (18.2.2) is to treat a failed `git rev-list` as an *error*, not a skip. An exception forces the caller to handle it explicitly and cannot be silently re-collapsed into the falsy `if not new_commits(...)` back-merge check the way a `None` or an empty-ish sentinel could.
- A sentinel return (`()`-like marker) or an `Optional[tuple]` both keep the "empty means both things" ambiguity one identity-check away from recurring; an exception removes the emptiness overload entirely.
- Naming: exceptions carry the language's own kind marker — the `Error` suffix — so the name reads as a raised signal, not a value.

Scope guard for THIS task: only the *declaration* lands. `new_commits`'s body still returns `()` on non-zero exit, its docstring is left describing today's no-raise behavior, and `Versioner._next_staging` is untouched. The wiring is 18.2.2's job; here the new failure test is deliberately red.

## Tasks

### Phase 1: Declare the signal

- [x] **Task 1: Define `CommitCollectionError` on the collector's public surface**
  Files: `src/commits/collector.py`
  Add a module-level exception class `class CommitCollectionError(Exception)` alongside `EMPTY_TREE_SHA` (top of the module, before `GitCommitCollector`), with a one-line docstring stating it signals that a `git` invocation behind a collector query failed (non-zero exit) — as distinct from a query that legitimately found nothing. This is the public name the tests import.
  Do NOT change `new_commits`'s body, its `check=False`/`return ()`-on-failure logic, or its docstring — the type is declared, not raised. Do not touch any other method. Do not add or change any import in `Versioner` or any other consumer.

### Phase 2: Pin the contract with tests

- [x] **Task 2: Restate the three existing `new_commits` cases against the settled contract** (depends on Task 1)
  Files: `tests/commits/test_collector.py`
  The three cases `test_new_commits_empty_for_fast_forward_back_merge`, `test_new_commits_empty_for_merge_commit_back_merge`, and `test_new_commits_returns_staging_unique_non_merge_commits` must keep asserting exactly what they assert today (`result == ()` for the two back-merges, `result == (staging_sha,)` for staging-unique work). Restate them so the empty-tuple assertion is explicitly the *genuine empty range* branch of the new two-outcome contract — a short clarifying comment on each empty case noting the empty tuple means "no staging-unique work" and is distinct from a `git` failure. Do not weaken, retarget, or change the git-setup of any of the three; back-merge detection is narrowed by nothing here.

- [x] **Task 3: Add a red case asserting a `git` failure raises `CommitCollectionError`** (depends on Task 1)
  Files: `tests/commits/test_collector.py`
  Add `test_new_commits_raises_on_git_failure` (import `CommitCollectionError` from `src.commits.collector`). Drive a genuine non-zero `git rev-list` exit against a valid repo by passing an unresolvable `exclude_ref` — build a real one-commit repo via the `git_repo`/`commit_at` fixtures, then call `collector.new_commits(str(git_repo), base_sha, base_sha, "no-such-branch")` (the bogus `^no-such-branch` makes `git rev-list` exit non-zero), wrapped in `with pytest.raises(CommitCollectionError):`. This mirrors the spec's real-world failure mode (an unresolvable `exclude_ref` / corrupt mirror).
  This case MUST be red against today's implementation: the unchanged body returns `()` on the non-zero exit instead of raising, so `pytest.raises` sees no exception and the test fails — that redness is the deliverable, not a defect. Tasks 2's three cases and every other existing test in the module must still pass.
