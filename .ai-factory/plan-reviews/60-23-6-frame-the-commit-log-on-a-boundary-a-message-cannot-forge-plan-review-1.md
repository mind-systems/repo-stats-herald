# Plan Review: 23.6 — Frame the commit log on a boundary a message cannot forge

## Code Review Summary

**Files Reviewed:** plan + `src/commits/collector.py`, `tests/commits/test_collector.py`, `tests/commits/conftest.py`, governing spec `86-commit-record-framing.md`, roadmap line 23.6
**Risk Level:** 🟢 Low

### Context Gates

- **Governing spec (86)** — PASS. The spec leaves the framing form open (NUL-based, or an RS that only counts before a valid record head) but forbids a boundary a message can contain and forbids a sanitising/escaping layer. The plan picks the NUL-anchored form and justifies it against the stronger constraint: an RS-plus-hex-head boundary is still author-reachable from inside a message, whereas NUL is refused by git outright. Every spec guard maps to a plan guard — `parse_log` signature and `collect` behaviour unchanged (Task 2), field splitting / numstat / shortstat / subject-body joining untouched (`_parse_record`/`_parse_tail` left byte-for-byte, Tasks 2–3), body-carrying case covered as well as subject (Task 4), no unquoting layer added (stated design decision). Spec verification items 1–4 are each realised by a plan task.
- **Architecture** — PASS. The change is confined to the `commits/` feature module; no cross-feature dependency, no composition-root wiring, no new abstraction/interface introduced. Feature-modular OO with DI is respected (the constant/format edits and the parse-loop rewrite are internal to `GitCommitCollector`).
- **Rules** — PASS. `.ai-factory/RULES.md` is intentionally empty (no project counter-defaults). No `skill-context/aif-review/SKILL.md` present. No convention to enforce.
- **Roadmap** — PASS. Roadmap line 23.6 matches the plan title and the spec, and names the same guards (twelve existing tests stay green unedited, no unquoting layer). Linkage present via the `Spec:` tag to `86-commit-record-framing.md`.

### Critical Issues

None.

### Verification performed

The plan's core parsing claim was checked against real git, not just reasoned about:

- **RS survives in a message.** `git commit -m "sub\x1eject"` and `-m "subject" -m "bo\x1edy"` both store the `\x1e` byte verbatim (`%s`/`%b` echo it back); git's default `-m` whitespace-cleanup does not strip RS. This validates Task 4's premise and its exact `-m` invocations.
- **The NUL-anchored stream splits and regroups as the plan describes.** Capturing `git log --numstat --shortstat --pretty=format:'%x00%H%x00%an%x00%s%x00%b%x00'` over a two-commit repo (second subject carrying `\x1e`) and splitting on NUL yields `["", H1, an1, s1, "", tail1, H2, an2, s2, "", tail2]` — one leading empty field, then exactly five fields per commit. Dropping the single leading `""` and chunking by five reconstructs `H\x00an\x00s\x00b\x00tail` for each record, exactly what `_parse_record` (`split(_FIELD_SEP, 4)`) still expects. Both commits parse; the `\x1e` byte lands in the subject field untouched.
- **The empty-body subtlety is handled correctly.** Empty `%b` produces a genuine empty field per commit (fields 5 and 10 above). The plan drops only *one leading* empty field and groups strictly by five — it does **not** filter empty fields globally — so empty bodies are preserved and not miscounted. This is the one place a naive rewrite would break, and the plan gets it right explicitly.
- **Field count is always a multiple of five after the drop.** Each commit emits exactly five `%x00`, so N commits give 5N NUL bytes → 5N+1 fields → 5N after the leading drop. No partial trailing group arises for well-formed git output; the plan's fallback (rely on `_parse_record` returning `None` for a short group) is correct belt-and-suspenders, not load-bearing.
- **`_RECORD_SEP` removal is safe.** Grepped the whole tree: the only reference is the old `parse_log` split at `collector.py:314`. Task 3's claim is confirmed; deleting it after Task 2 breaks nothing.
- **Fixtures and helpers named in Task 4 exist as described.** `git_repo` and `commit_at` live in `tests/commits/conftest.py`; the module-level `_git(*args, cwd)` helper and the `collector` fixture live in `tests/commits/test_collector.py`. The plan's example `_git("-c", "user.name=herald-test", …, cwd=git_repo)` matches the helper's signature. The current file holds exactly twelve tests (none exercise `collect`/`parse_log` yet), so "twelve existing tests" is accurate and the new tests are strictly additive.

### Positive Notes

- The design decision section is exemplary: it names the rejected alternative (RS-plus-hex-head), states *why* it fails the unforgeability bar, and proves the NUL invariant rests on three independent facts (message, path, and stat tail all cannot contain NUL). This is precisely the reasoning the spec asks the task to own.
- Minimal-blast-radius framing: `_parse_record` and `_parse_tail` are frozen, so the change is provably "how records are found," not "what a record parses into" — the exact spec guard. The join-then-resplit round-trip (`_FIELD_SEP.join(group)` handed to a method that re-splits on `_FIELD_SEP`) is a small redundancy consciously accepted to keep `_parse_record` untouched; the right trade for this guard.
- Empty-input behaviour is called out and correct (`"".split("\x00") == [""]` → leading drop → no records → empty tuple), preserving the prior no-raise contract.
- Task 4 mirrors the two spec verification cases (subject-carrying and body-carrying) end-to-end through real-repo fixtures, matching the silent-failure surface the spec flags as must-cover, and pins committer identity so the tests are reproducible.

The comment-line anchors in Task 1 ("lines 7–10") and Task 3 ("lines 12–14") are approximate — the placeholder comment is lines 7–9 with `_PRETTY_FORMAT` on line 10, and the RS/NUL comment is line 12 with the constants on 13–14 — but each task also identifies its target semantically ("the literal-placeholder comment above `_PRETTY_FORMAT`", "the adjacent comment"), so the intent is unambiguous and the implementer reconciles against the file they must read anyway. Immaterial, not a defect.

PLAN_REVIEW_PASS
