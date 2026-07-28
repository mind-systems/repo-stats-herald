# GitCommitCollector.collect — Test Plan

**Date:** 2026-07-29
**Source:** roadmap-test-coverage agent

## Source Overview

`GitCommitCollector.collect` (`src/commits/collector.py`) runs one `git log --numstat --shortstat --pretty=format:'%x1e%H%x00%an%x00%s%x00%b%x00'` call, splits stdout on the RS byte into per-commit records, and hands each to `_parse_record`, which splits on NUL with `maxsplit=4` into `[sha, author, subject, body, tail]` and delegates the tail to `_parse_tail`. `_parse_tail` line-scans the stat block with two regexes — `_NUMSTAT_RE` (`added\tdeleted\tpath`, `-` allowed for binary) feeding `changed_files`, and `_SHORTSTAT_RE` (` N files changed…`) feeding `diffstat`. The result is a `CommitContext(repo, branch, commits)` whose `Commit`s are the sole input to `PromptBuilder.build`, `LinkedChangeResolver`, and the episodic backfill — every parse error becomes prose, never an exception.

## Instantiation

Reuse the existing fixtures; do not add a new repo fixture.

- `collector` — module-local fixture in `tests/commits/test_collector.py`; a bare `GitCommitCollector()`.
- `git_repo` — `tests/commits/conftest.py`; a throwaway `tmp_path/repo` initialized with `git init -b main`, so branch name and location are deterministic without ambient config.
- `commit_at` — `tests/commits/conftest.py`; `(repo, message, when=None) -> sha`, commits with pinned identity `herald-test <herald@test.invalid>` and optional `GIT_AUTHOR_DATE`/`GIT_COMMITTER_DATE`, returning the new SHA.
- Existing module-level helpers in `test_collector.py` are also reusable as-is: `_git`, `_checkout_new_branch`, `_checkout`, `_merge(repo, branch, message, no_ff)`, `_tag`.

**Critical instantiation caveat:** `commit_at` commits with `--allow-empty` and never writes or stages a file, so every commit it produces on its own has *zero* numstat lines and *no* shortstat line. Any test that exercises the actual `--stat` parse must first write a file under `git_repo` and stage it with the existing `_git("add", "-A", cwd=git_repo)` helper; `commit_at` then commits the staged index. Only the deliberate zero-file case should call `commit_at` with nothing staged.

## Existing Coverage

`tests/commits/test_collector.py` contains exactly 12 tests, and **none of them calls `collect()`, `_collect_commits`, `_parse_record`, or `_parse_tail`**. Verified test-by-test:

- `commit_at_or_before` — 2 tests
- `active_branches` — 2 tests
- `list_tags` — 2 tests
- `is_ancestor` — 3 tests (true / false / unknown-ref-no-raise)
- `new_commits` — 3 tests (fast-forward back-merge, merge-commit back-merge, staging-unique commits)

So the `--stat` parse that feeds every downstream prompt has **zero** automated coverage today. Neither is any of `first_parent_steps`, `changed_paths`, `read_blob`, `commit_timestamp`, or `_current_branch` covered — but those are outside this plan's scope. The only recorded verification of `collect()` is a one-off manual run captured in `.ai-factory/reviews/03-commits-feature-review-1.md`.

## Test Cases

### Record framing (RS split, empty leading record, ordering)

1. **should return one Commit per commit in the range, newest-first, when the range spans several commits** — `collect` → `_collect_commits`. Assert the SHA tuple equals the fixture SHAs reversed (git log is newest-first and the collector preserves that order).
2. **should not emit a phantom empty Commit for the leading record separator when parsing any non-empty range** — `_collect_commits`'s `if not record.strip()` guard. The format prefixes every record with `%x1e`, so `split` always yields an empty leading element.
3. **should return an empty commits tuple without raising when the range is well-formed but empty** — `collect`. Setup: `collect(str(git_repo), f"{sha}..{sha}")`; assert `ctx.commits == ()` and `ctx.branch == "main"`.
4. **should not silently drop a commit whose subject contains the record-separator byte** — `_collect_commits`/`_parse_record`. Setup: `commit_at(git_repo, "fix\x1ething")`. **Expected red:** today the RS splits the record into two fragments, each with fewer than 5 NUL fields, so `_parse_record` returns `None` for both and the commit vanishes from `CommitContext` entirely — a whole commit missing from the narration with no error. Non-obvious: a NUL byte in a message is impossible (git rejects it), so there is deliberately **no** NUL-in-message case.

### Subject/body joining

5. **should join subject and body as `subject\n\nbody` when the commit has a multi-line body** — `_parse_record`. `body` is `.strip()`ed, so trailing newlines must not survive.
6. **should set message to the subject alone when the commit body is empty** — `_parse_record` (`body.strip()` falsy branch).
7. **should not leak a body line that looks like a numstat line into changed_files** — `_parse_record` field isolation + `_parse_tail`. Setup: stage one real file, then commit with a body containing a literal `12\t3\tfake/injected.py` line. Assert `changed_files` is the real path only. This is the NUL-delimiting guarantee — if it ever regresses, a crafted commit message injects fabricated file paths into every prompt.
8. **should not overwrite diffstat with a body line that looks like a shortstat summary** — `_parse_tail`'s last-match-wins assignment. Setup: body containing ` 99 files changed, 999 insertions(+), 999 deletions(-)`.

### changed_files / diffstat extraction

9. **should populate changed_files with every touched path and diffstat with the shortstat line when a commit touches several files** — `_parse_tail`. Assert the exact path tuple and that `diffstat` has no leading space (the raw git line is space-prefixed; the code strips it).
10. **should return the full untruncated path when a commit touches a deeply nested long path** — `_parse_tail`. Setup: a path well over 80 characters. Assert it does not start with `...`. This is the entire reason `--numstat` was chosen over `--stat`; a regression to `--stat` would truncate silently.
11. **should include a binary file in changed_files when git renders its numstat counts as `-`** — `_NUMSTAT_RE`'s `(?:\d+|-)` alternation. Assert `diffstat` reports `1 file changed` (singular — `_SHORTSTAT_RE` allows `files?`).
12. **should keep git's brace-compressed rename form verbatim when a commit renames a file inside a directory** — `_parse_tail`. **Non-obvious:** the plan says git renders a rename as `old => new`, but real `git log --numstat` emits the *compressed* form `docs/{spec => behavior}/a.md` for shared-prefix renames and `a.md => b.md` only for a flat rename. The assertion must pin the actual emitted string, not the plan's wording. Consequence if it drifts: `changed_files` holds a path that exists nowhere in either tree, and downstream `read_blob`/`SourceStrategy.selects` lookups on it all miss.
13. **should keep changed_files empty and diffstat empty when a commit touches zero files** — `_parse_tail` with an empty stat block. Assert the commit is still present (it must not be dropped).
14. **should keep changed_files empty and diffstat empty for a merge commit without raising** — `_parse_record`/`_parse_tail`. Reuse `_checkout_new_branch` + `_merge(..., no_ff=True)`. `git log --numstat` emits no per-file stats for a merge without `-m`; assert the merge commit is present with empty stats and the sibling non-merge commits still parse correctly.
15. **should capture every path without truncation or dropping when the diffstat is very large** — `_parse_tail` over a long tail. Setup: 250 files in one commit.
16. **should preserve a path containing spaces intact** — `_NUMSTAT_RE`'s `(.+)$` capture. Setup: `my notes/file one.md`.
17. **should return a non-ASCII path literally rather than C-quoted with octal escapes** — `_collect_commits`' git invocation. Setup: a file named `документ.md`. **Expected red:** `collect` does *not* pass `-c core.quotepath=false`, and git's default emits `"\320\264\320\276..."`. The sibling method `changed_paths` explicitly sets that flag with a comment stating why — `collect` is asymmetric with it.

### Range semantics

18. **should return the whole reachable history when `before` is the EMPTY_TREE_SHA sentinel** — `collect`. Verified against real git: `git log <empty-tree>..HEAD` exits 0 and yields the full history. This pins the root-commit step that `first_parent_steps` hands to `EpisodicBackfill` and `LinkedChangeResolver`. Note that `collect` needs **no** empty-tree special case, unlike `active_branches`/`commit_timestamp`, which do — that asymmetry is the point of the test.
19. **should raise CalledProcessError when the revision range is unknown or malformed** — `_collect_commits` runs with `check=True`, and the governing plan mandates fail-loud on a bad range rather than an empty context. Keep the assertion strictly about `collect`; see the scope guard below.

### CommitContext shape and author

20. **should set repo to the given repo_path verbatim and branch to the checked-out branch** — `collect`/`_current_branch`. Assert `ctx.repo == str(git_repo)` (not resolved, not basenamed); both are rendered into the prompt header by `PromptBuilder.build`.
21. **should report branch as `HEAD` when the repo is in detached-HEAD state** — `_current_branch`. `rev-parse --abbrev-ref HEAD` returns the literal string `HEAD`, which becomes a plausible-but-wrong branch label in the narration with no error. Pin whichever behavior the contract wants; today it is the literal `"HEAD"`.
22. **should preserve a non-ASCII author name exactly as `%an` emits it** — `_parse_record`. The `commit_at` fixture pins `user.name=herald-test`, so this case needs its own commit via the module-level `_git` helper with `-c user.name=…`.
23. **should preserve a non-ASCII commit message exactly** — `_parse_record`. `text=True` decodes with the locale encoding, so this is the case that catches a C-locale/ASCII decode regression in CI.

**On timestamp parsing:** `Commit` has no timestamp field and `collect` never parses a date — the pretty format carries only `%H/%an/%s/%b`. All timestamp parsing lives in `commit_timestamp`, which is *not* part of this scope.

## Gotchas

- **`commit_at` makes empty commits.** The conftest fixture passes `--allow-empty` and never writes a file, so a naive `commit_at`-only test asserts nothing about the stat parse. Stage real files first with `_git("add", "-A", cwd=git_repo)`.
- **git compresses renames.** `--numstat` emits `dir/{old => new}/file.md` for shared-prefix renames and `old.md => new.md` only for flat ones — confirmed empirically against this repo's history. The governing plan's `old => new` wording is inaccurate; assert the real emission.
- **`core.quotepath` defaults to true.** Any path byte ≥ 0x80 comes back double-quoted with octal escapes from `git log --numstat`. `collect` does not disable it, while the sibling `changed_paths` explicitly does.
- **Binary files carry `-` counts.** `-\t-\tpath` is a valid numstat line and must still contribute a `changed_files` entry.
- **The shortstat line is space-prefixed** and uses `file`/`files` singular/plural; `_SHORTSTAT_RE` tolerates both and `_parse_tail` strips the leading space. Assert the stripped form.
- **Merge commits emit no per-file stats** without `-m`/`--first-parent`, so empty stats on a merge is correct git behavior, not a parse failure.
- **The RS byte is legal in a commit message; NUL is not.** Only the RS case is testable, and it is the one that can make an entire commit disappear.
- **Ordering is newest-first**, inherited from `git log`; `_collect_commits` does not re-sort.
- **The empty-tree SHA needs no special case in `collect`**, unlike `active_branches`, which guards it explicitly because `commit_timestamp` would blow up on the tree header.
- **SCOPE GUARD — excluded from this plan.** `new_commits`' failure-vs-empty-range signal is owned by OPEN roadmap tasks 18.2.1 and 18.2.2 (`.ai-factory/specs/65-collector-failure-signal-contract.md`, `.ai-factory/specs/54-git-failure-vs-empty-range.md`). Those tasks own the three existing `new_commits` tests plus the new genuine-`git`-failure case. **No test here touches `new_commits`, `Versioner._next_staging`, or the failure-signal shape.** Case 19 above asserts `collect`'s own long-standing `check=True` fail-loud contract only and must not be generalized into a collector-wide failure-signal assertion, or it will collide with 18.2.2 when that lands.

## Refactor Required

`collect` takes only `repo_path` / `rev_range` and reaches git's stdout inside `_collect_commits` through a module-level `subprocess.run`. The shapes this parse is actually about are the ones no argument reaches:

- A record-separator byte inside a commit subject — handled by the RS split *above* `_parse_record`, so no parameter carries it.
- C-quoted non-ASCII numstat paths, whose form depends on the ambient `core.quotepath` setting, which arrives through neither the `git_bin` constructor param nor the call.

Both therefore cost a `monkeypatch.setattr` on the collector module's `subprocess`, or a hand-built repo plus git-config neutralization, before a single assertion can be written.

**Two changes, and the post-refactor API the test implementer should expect:**

1. **Expose the raw `git log` text as a value the API accepts.** Either a public `parse_log(stdout: str, repo: str, branch: str) -> CommitContext` seam that `collect` calls after shelling out, or the log-runner passed as a constructor callable. With the first shape, every parsing case in this plan becomes a pure string-in / `CommitContext`-out test with no git, no fixture repo, and no patching; `collect` keeps its current signature and gains one line delegating to `parse_log`. Cases 4 (RS byte in subject), 7–8 (numstat/shortstat injection via the body), 12 (rename form), 14 (merge commit), and 15 (250-file diffstat) all move onto the pure seam. Cases 1–3, 9–11, 13, 16–23 can stay on the real-repo fixtures, which remain the honest end-to-end check that git's actual output matches what the parser expects.
2. **Pin `-c core.quotepath=false` on the `log` invocation**, as the sibling `changed_paths` already does. This makes path shape a parameter of the code rather than of the machine, and turns case 17 from an expected-red into a straightforward assertion.

Guard: `collect`'s public signature and return type do not change. `parse_log` is additive.
