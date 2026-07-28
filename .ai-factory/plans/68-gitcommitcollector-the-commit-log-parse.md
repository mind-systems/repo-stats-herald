# Test Plan: GitCommitCollector — the commit-log parse

## Context
`GitCommitCollector.collect` / `parse_log` (`src/commits/collector.py`) turns raw `git log --numstat --shortstat` output into the `CommitContext` that is the sole input to `PromptBuilder.build`, `LinkedChangeResolver`, and the episodic backfill. Every parse error becomes wrong prose, never an exception, and today the parse has zero automated coverage — the 12 existing tests cover only ranges, tags, ancestry, and `new_commits`. This plan splits the parse surface into a **parse group** driven by captured text constants through `parse_log`, and a **collect group** driven by the existing repository fixtures through `collect`.

## Settings
- Testing: yes
- Logging: minimal
- Docs: no

## Test Command
`uv run pytest tests/commits/test_parse_log.py tests/commits/test_collect.py`

## Target Spec Files
Two new modules (the "split" the roadmap line calls for):
- `tests/commits/test_parse_log.py` — parse group; pure string-in / `CommitContext`-out, no git, no fixture repo.
- `tests/commits/test_collect.py` — collect group; the honest end-to-end check that real git output still matches the parser, on the `git_repo` / `commit_at` fixtures.

`tests/commits/test_collector.py` stays untouched — it owns the ranges/tags/ancestry/`new_commits` tests.

## Fixtures & helpers (reuse only — add no new repo fixture)
- **`git_repo`** and **`commit_at`** already live in `tests/commits/conftest.py` and are shared across the package; the collect group requests them directly.
- **`collector`** is a module-local `GitCommitCollector()` fixture in `test_collector.py`. Redefine an identical one-line fixture in each new module (a bare `GitCommitCollector()`); do not import it across test modules.
- **Module-level helper `_git`** — `tests/commits/conftest.py:11` **already** defines a reusable `_git(*args, cwd, env=None)` (a superset of the `env`-less one in `test_collector.py`). The collect group needs only `_git` (staging via `add -A`, non-ASCII author commits with `-c user.name=…`, and putting the repo into detached-HEAD state). Use the existing conftest `_git` or redefine one locally in the new module — **do not overwrite or shadow the conftest definition**, whose `env` parameter is load-bearing for `commit_at(when=…)` (via `_commit`). No runtime test in either new module needs `_merge`/`_checkout_new_branch`: the one merge scenario (case 14, Task 3) is captured **once, offline, from real git output** and asserted as a text constant, so no merge helper runs at test time. This is setup, not a test task.

### Critical instantiation caveats (from the spec — read before writing collect-group tests)
- **`commit_at` makes *empty* commits.** It passes `--allow-empty` and never writes or stages a file, so a `commit_at`-only commit has zero numstat lines and no shortstat line. Any test that exercises the `--stat` parse must first write a real file under `git_repo` and stage it with `_git("add", "-A", cwd=git_repo)`; `commit_at` then commits the staged index. Only the deliberate zero-file case (case in Task 5) calls `commit_at` with nothing staged.
- **`_run_log` now sets `-c core.quotepath=false`**, so git emits non-ASCII path bytes literally — case 17 is a straight positive assertion, not expected-red.
- **git compresses renames.** `git log --numstat` emits the compressed form `dir/{old => new}/file.md` for a shared-prefix rename and `old.md => new.md` only for a flat rename. Assert the actual emitted string, never the "old => new" wording.

## Scope guards (do not cross)
- **`new_commits`, `Versioner._next_staging`, and the failure-signal shape stay untouched** — they belong to open tasks 18.2.1 / 18.2.2. Case 19 (Task 7) asserts `collect`'s own long-standing `check=True` fail-loud contract only; do not generalize it into a collector-wide failure-signal assertion.
- **The record-separator-byte case (spec case 4) is out of scope and already landed.** Commit `d47f195` (task 23.6) fixed the framing and shipped its two positive regression tests (`test_collect_keeps_a_commit_whose_subject_contains_the_record_separator_byte` and the body variant) in `test_collector.py`. Do **not** re-add or duplicate them, and do not write a red assertion for the old vanish-a-commit defect.
- No test here edits `src/`.

## Tasks

### Phase 1: parse group — `parse_log` driven by captured text constants (`tests/commits/test_parse_log.py`)

Each case builds the raw log as a Python string literal (fields joined by `\x00`, records leading with the marker exactly as `_PRETTY_FORMAT` emits) and calls `GitCommitCollector().parse_log(text, repo="r", branch="main")`. For cases 12/14/15, capture the block **once** from real `git log --numstat --shortstat` output and store it as a module-level constant so the assertion pins git's real emission, not a hand-guessed shape.

- [x] **Task 1: subject/body joining (`_parse_record`)**
  Files: `tests/commits/test_parse_log.py`
  Test cases:
  - `should join subject and body as "subject\n\nbody" when a record has a multi-line body`
  - `should strip trailing whitespace from the body so no blank tail survives in the message` (`body.strip()` — a trailing newline must not leak into `message`)
  - `should set message to the subject alone when a record's body field is empty` (the `body.strip()`-falsy branch)

- [x] **Task 2: field-isolation injection guards (`_parse_record` NUL isolation + `_parse_tail`)**
  Files: `tests/commits/test_parse_log.py`
  Test cases:
  - `should keep changed_files to the real numstat paths when a body field contains a line shaped like "12\t3\tfake/injected.py"` (the NUL-delimiting guarantee — a crafted message must not inject a fabricated path into `changed_files`)
  - `should not overwrite diffstat when a body field contains a line shaped like " 99 files changed, 999 insertions(+), 999 deletions(-)"` (guards `_parse_tail`'s last-match-wins assignment against body content)

- [x] **Task 3: numstat/shortstat extraction over real captured blocks (`_parse_tail`)**
  Files: `tests/commits/test_parse_log.py`
  Test cases:
  - `should keep git's brace-compressed rename path verbatim (e.g. "docs/{spec => behavior}/a.md") when a captured record renames a file inside a directory` (pin the actual emitted compressed form; if it drifts, `changed_files` holds a path present in neither tree and downstream `read_blob` misses)
  - `should return empty changed_files and empty diffstat for a merge record while the sibling non-merge records in the same log still parse` (`git log --numstat` emits no per-file stats for a merge without `-m`; empty stats is correct, not a parse failure — assert the merge commit is present *and* its siblings parsed)
  - `should capture every path without truncation or dropping when a captured record's stat block lists 250 files` (long-tail `_parse_tail`; assert the full path count and no truncation)

### Phase 2: collect group — `collect` driven by the repository fixtures (`tests/commits/test_collect.py`)

- [x] **Task 4: record framing, ordering, empty range (`collect` / `_run_log` / `parse_log` end-to-end)**
  Files: `tests/commits/test_collect.py`
  Test cases:
  - `should return one Commit per commit newest-first when the range spans several commits` (assert the SHA tuple equals the fixture SHAs reversed — git log is newest-first and the collector preserves that order)
  - `should not emit a phantom empty Commit for the leading NUL marker when the range is non-empty` (`_PRETTY_FORMAT` prefixes every record with a `%x00` marker, so `log_text.split("\x00")` always yields an empty leading field; assert the commit count excludes it)
  - `should return an empty commits tuple and branch "main" without raising when the range is well-formed but empty` (setup: `collect(str(git_repo), f"{sha}..{sha}")`; assert `ctx.commits == ()` and `ctx.branch == "main"`)

- [x] **Task 5: changed_files / diffstat extraction on real git output (`_parse_tail`)**
  Files: `tests/commits/test_collect.py`
  (Stage real files with `_git("add", "-A", cwd=git_repo)` before committing — except the zero-file case.)
  Test cases:
  - `should populate changed_files with every touched path and set diffstat to the space-stripped shortstat line when a commit touches several files` (assert the exact path tuple and that `diffstat` has no leading space — the raw git line is space-prefixed and the code strips it)
  - `should return the full untruncated path when a commit touches a path well over 80 characters` (assert it does not start with "..." — the whole reason `--numstat` was chosen over `--stat`)
  - `should include a binary file in changed_files and report "1 file changed" when git renders its numstat counts as "-"` (the `(?:\d+|-)` alternation; singular "file" via `_SHORTSTAT_RE`'s `files?`)
  - `should keep changed_files and diffstat empty while keeping the commit present when a commit touches zero files` (the only `commit_at`-with-nothing-staged case; assert the commit is still present, not dropped)
  - `should preserve a path containing spaces intact` (setup: `my notes/file one.md`; the `(.+)$` capture)

- [x] **Task 6: non-ASCII path, author, and message round-trip (`_run_log` / `_parse_record`)**
  Files: `tests/commits/test_collect.py`
  Test cases:
  - `should return a non-ASCII path literally rather than C-quoted with octal escapes` (setup: a file named `документ.md`; positive assertion now that `_run_log` sets `core.quotepath=false`)
  - `should preserve a non-ASCII author name exactly as %an emits it` (needs its own commit via `_git` with `-c user.name=…`, since `commit_at` pins `herald-test`)
  - `should preserve a non-ASCII commit message exactly` (catches a C-locale/ASCII decode regression under `text=True`)

- [x] **Task 7: range semantics (`collect`)**
  Files: `tests/commits/test_collect.py`
  Test cases:
  - `should return the whole reachable history when before is the EMPTY_TREE_SHA sentinel` (import `EMPTY_TREE_SHA`; `git log <empty-tree>..HEAD` yields the full history — `collect` needs no empty-tree special case, and that asymmetry with `active_branches` is the point)
  - `should raise CalledProcessError when the revision range is unknown or malformed` (`_run_log` runs `check=True`; assert strictly about `collect`, do not generalize to a failure-signal contract — see scope guards)

- [x] **Task 8: CommitContext shape and branch label (`collect` / `_current_branch`)**
  Files: `tests/commits/test_collect.py`
  Test cases:
  - `should set repo to the given repo_path verbatim and branch to the checked-out branch` (assert `ctx.repo == str(git_repo)` — not resolved, not basenamed; both render into the prompt header)
  - `should report branch as "HEAD" when the repo is in detached-HEAD state` (`rev-parse --abbrev-ref HEAD` returns the literal `"HEAD"`; pin today's behavior — a plausible-but-wrong branch label with no error)

## Notes on omitted surfaces
- No timestamp case: `Commit` has no timestamp field and `collect` never parses a date (the pretty format carries only `%H/%an/%s/%b`). All date parsing lives in `commit_timestamp`, outside this scope.
- `first_parent_steps`, `changed_paths`, `read_blob`, `commit_timestamp`, and `_current_branch`'s enumeration siblings are outside this plan.
