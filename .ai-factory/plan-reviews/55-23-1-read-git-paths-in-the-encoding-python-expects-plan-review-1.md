## Plan Review Summary

**Plan:** 23.1 — Read git paths in the encoding Python expects
**Files Reviewed:** plan + `src/commits/collector.py` + spec `.ai-factory/specs/81-git-path-quoting-normalization.md` + ROADMAP line 124
**Risk Level:** 🟢 Low

### Context Gates
- **Roadmap:** WARN-free. The plan's `# Plan:` heading resolves cleanly to ROADMAP.md:124 (`23.1 — Read git paths in the encoding Python expects`), whose `Spec:` tag points to `.ai-factory/specs/81-git-path-quoting-normalization.md`. Plan, contract line, and spec agree on scope, guards, and the "land 23.1 before 23.2" ordering.
- **Architecture:** No boundary or dependency concern — the change is a single argument added to a subprocess invocation inside the class that already owns all git-command details (`GitCommitCollector` in `src/commits/`), consistent with "git-command details stay inside `GitCommitCollector`."
- **Rules:** No `.ai-factory/RULES.md` violation surfaced; the edit adds no plan-layer references to code comments (none are added at all).

### Critical Issues
None.

### Verification against ground truth
- **File path correct.** `src/commits/collector.py` exists and contains `GitCommitCollector._collect_commits`.
- **Line reference correct.** `_collect_commits` spans lines 308–332; the `subprocess.run([...])` invocation is lines 309–324, matching the plan's "~308–324".
- **Sibling reference correct.** `changed_paths` (lines 82–99) places the flag as the two-element pair `"-c", "core.quotepath=false"` immediately after `self._git_bin` and before `-C` (lines 84–86), and carries the explanatory comment (lines 78–80). The plan's instruction to add it "immediately after `self._git_bin` … exactly as the sibling `changed_paths` method already does (its `-c`, `core.quotepath=false` pair sits before `-C`)" reproduces this precisely. This placement is also technically required: `-c` is a git *global* option and must precede the `log` subcommand.
- **Guards are faithful to the spec.** The plan's five guards (invocation-only; no unquoting logic; byte-identical ASCII output; do not edit `changed_paths`; keep the edit minimal for 23.2) map one-to-one onto the spec's Guards section. The named untouchables — `_parse_tail`, `_parse_record`, `_NUMSTAT_RE`, `_SHORTSTAT_RE` — all exist at lines 352, 334, 16, 17 respectively, so the "do not touch" list references real symbols.
- **Correctness of the fix.** `git log --numstat` with default `core.quotepath=true` octal-escapes and double-quotes non-ASCII path bytes; `-c core.quotepath=false` renders them literally. Since `capture_output` uses `text=True` (UTF-8 decode), literal bytes then decode to the real path — making `Commit.changed_files` entries equal to what `changed_paths` reports, which is exactly the spec's verification criterion.
- **Scope boundary is right.** Rename-arrow and embedded-newline/quote quoting are correctly declared out of scope; the plan adds no unquoting logic and leaves the numstat parsing untouched, so an all-ASCII repo yields byte-identical output.

### Positive Notes
- The plan pins the exact insertion point, the exact token form (two list elements, not one `"-c core.quotepath=false"` string), and the exact anchor method, leaving no ambiguity for the implementer — no fantasy holes.
- It explicitly preserves the minimal footprint for the follow-on 23.2 edit on the same invocation, honoring the ordering constraint carried in both the spec and the roadmap line.

PLAN_REVIEW_PASS
