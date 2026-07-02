# Plan: commits/ feature

## Context
Introduce the `commits/` feature package: immutable domain value objects (`Commit`, `CommitContext`) and a `GitCommitCollector` that reads a revision range from a local git repo (read-only), producing domain objects the summarization feature will later depend on.

## Settings
- Testing: no
- Logging: minimal
- Docs: no

## Tasks

### Phase 1: Domain models

- [x] **Task 1: Create the commits feature package + domain models**
  Files: `src/commits/__init__.py`, `src/commits/models.py`
  Create an empty `src/commits/__init__.py` to mark the package (follow the pattern of `src/core/__init__.py`).
  In `models.py`, define two immutable value objects using `@dataclass(frozen=True, slots=True)`:
  - `Commit` with fields `sha: str`, `author: str`, `message: str`, `changed_files: tuple[str, ...]`, `diffstat: str`. `message` holds subject + body combined; `diffstat` holds a summary line like `"3 files changed, 40 insertions(+), 5 deletions(-)"` (empty string allowed).
  - `CommitContext` with fields `repo: str` (repo name or path label), `branch: str`, `commits: tuple[Commit, ...]`.
  No behavior/logic — pure data. Use `tuple` (not `list`) so instances stay hashable/immutable. Match the Python 3.12 style already used in `src/core/config.py` (built-in generics, `X | None`).

### Phase 2: Git collector

- [x] **Task 2: Implement GitCommitCollector.collect** (depends on Task 1)
  Files: `src/commits/collector.py`
  Define a plain class `GitCommitCollector` with a `collect(self, repo_path: str, rev_range: str) -> CommitContext` method. Optionally accept a git binary path in `__init__` (default `"git"`) for testability — no other constructor dependencies.
  Implementation shells out to git **read-only** via `subprocess.run(<arg list>, capture_output=True, text=True, check=True)` — always an **argument list, never `shell=True`**, so no shell interpolation is possible. Always pass `-C <repo_path>` so the working directory is never changed:
  - Current branch: `git -C <repo> rev-parse --abbrev-ref HEAD`.
  - Commit metadata + file stats + summary in one call:
    `git -C <repo> log --numstat --shortstat --pretty=format:<FMT> --end-of-options <rev_range>`
    where `<FMT>` uses a NUL field separator, e.g. `%x1e%H%x00%an%x00%s%x00%b%x00` (a record separator `%x1e` between commits + NUL `%x00` between fields), so arbitrary commit-message text parses cleanly without relying on spaces/newlines.
    - **Do not use `--stat`**: it abbreviates long paths with a leading `...` and column-truncates to terminal width, silently corrupting `changed_files`. Use the machine-readable outputs instead.
    - `changed_files` ← the `--numstat` lines (`added\tdeleted\tpath`), taking the full untruncated `path` field, collected into `tuple[str, ...]`.
    - `diffstat` ← the `--shortstat` summary line (`N files changed, X insertions(+), Y deletions(-)`).
    - Renames: `--numstat` renders a rename as `old => new` in the path field. Parse it explicitly — for now keep the whole `old => new` string as the path (documented as-is); do not silently mangle it.
  - Parse each record into `sha`, `author`, `message` (subject + body joined), `changed_files`, and `diffstat`.
  Return a fully-populated `CommitContext(repo=repo_path, branch=<branch>, commits=(...))`.
  Keep all git-command details and parsing encapsulated inside this class — it returns domain objects, never raw git strings. Do not introduce a `Collector` ABC yet (defer until the GitHub collector lands).

- [x] **Task 3: Add defensive guards for empty ranges and merge commits** (depends on Task 2)
  Files: `src/commits/collector.py`
  Harden parsing so the collector never crashes and never mutates or touches the network:
  - Empty revision range (valid range, no commits) → `git log` exits 0 with empty output → return `CommitContext` with an empty `commits` tuple, not an error.
  - Malformed/unknown range → `git log` exits non-zero and `check=True` raises `CalledProcessError`; **propagate it** (fail loud on a bad range). "Never crashes" (this task) means well-formed-but-empty input is handled gracefully — it does not mean swallowing bad-range errors.
  - Commits with an empty body must parse (message falls back to just the subject).
  - Merge commits (multiple parents, no per-file stats emitted by default without `-m`) must not raise — `changed_files` becomes an empty tuple and `diffstat` an empty string when git emits none.
  - The format prefixes each record with the record separator (`%x1e`), so splitting on `%x1e` yields an **empty leading element**. Drop empty/whitespace-only records **regardless of position** (leading or trailing) — do not blindly index `[0]`.
  Only read-only git subcommands are permitted (`log`, `rev-parse`) — no fetch/pull/push or any writing subcommand. `rev_range` is always passed after `--end-of-options` so a value beginning with `-` cannot be interpreted as a git option.
  Verify manually: `GitCommitCollector().collect(".", "HEAD~3..HEAD")` on this repo returns a `CommitContext` whose `commits` has 3 entries with non-empty `sha`, `author`, `message`, `changed_files`, and `diffstat` for real (non-merge) commits, and each entry in `changed_files` is a **full, untruncated** path (no leading `...`).
