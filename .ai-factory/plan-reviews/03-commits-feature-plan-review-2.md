# Plan Review 2: commits/ feature (03-commits-feature.md)

## Code Review Summary

**Files Reviewed:** plan (3 tasks) + targeted codebase (`src/core/config.py`, `src/__init__.py`, `src/core/__init__.py`, `ARCHITECTURE.md`, `ROADMAP.md`, `.ai-factory/rules/base.md`, spec note `notes/03-commits-feature.md`, live `git log` behavior on this repo with git 2.50.1)
**Risk Level:** 🟢 Low

This is the second pass. **All four issues raised in review 1 have been fully incorporated into the plan.** The remaining notes are non-blocking drift in *other* artifacts (roadmap contract line, stale rules) plus one small implementation-guidance clarification. Nothing blocks implementation.

---

### Review-1 Follow-up (all resolved)

- **#1 `--stat` path truncation → fixed.** Task 2 now uses `--numstat --shortstat`, explicitly forbids `--stat`, sources `changed_files` from the full untruncated `--numstat` path field and `diffstat` from the `--shortstat` summary line, and the Task 3 verify now requires "each entry in `changed_files` is a **full, untruncated** path (no leading `...`)". Verified against live output: `--numstat` emits real paths (`.ai-factory/plan-reviews/02-settings-layer-plan-review-1.md`), `--shortstat` emits the clean ` N files changed, X insertions(+), Y deletions(-)` line.
- **#2 Leading empty record → fixed.** Task 3 now says "Drop empty/whitespace-only records **regardless of position** (leading or trailing) — do not blindly index `[0]`." Confirmed the record separator prefixes the stream (`\x1e` at position 0), so the split yields an empty leading element.
- **#3 Options injection via `rev_range` → fixed.** Task 2/3 now pass `rev_range` after `--end-of-options`, and mandate an **argument list, never `shell=True`** with `capture_output=True, text=True`. `--end-of-options` is supported by this git version.
- **#4 `check=True` vs empty-range → fixed.** Task 3 now distinguishes explicitly: valid-but-empty range → exit 0, empty output → empty `commits` tuple; malformed/unknown range → non-zero exit → `CalledProcessError` propagated ("fail loud on a bad range"). The "never crashes" language is scoped to well-formed-but-empty input.

---

### Context Gates

- **Architecture (`ARCHITECTURE.md`)** — ✅ PASS. Plan follows the feature-modular layout: `src/commits/` owns `models.py` + `collector.py`; no root-level `models/` dump. `GitCommitCollector` is a plain class returning domain objects — the swappable seam for a future `GitHubCommitCollector`. Deferring the `Collector` ABC matches principle #4 ("introduce an ABC when a real second implementation is imminent — not speculatively"). Package marker matches the existing pattern (`src/__init__.py`, `src/core/__init__.py` are both 0-byte files).
- **Rules (`.ai-factory/rules/base.md`)** — ⚠️ WARN (non-blocking, unchanged from review 1). `base.md` still describes a layer-first structure (`src/routes/`, `src/services/`, `src/models/`, `src/config.py`) that contradicts the feature-modular `ARCHITECTURE.md` and the actual tree (`src/core/config.py`). The plan correctly follows the newer, more specific `ARCHITECTURE.md`. No action in this plan; `rules/base.md` should be reconciled with the architecture doc separately.
- **Roadmap (`ROADMAP.md`)** — ⚠️ WARN (non-blocking). The active task maps exactly to "**commits/ feature**" (Phase 1): `models.py` (immutable `Commit`, `CommitContext`) + `collector.py` (`GitCommitCollector.collect(repo_path, rev_range)`), read-only local git, empty-range/merge-commit guards, `HEAD~3..HEAD` verify. Linkage is present. **Drift:** the roadmap contract line still says "shelling read-only `git log --stat`" — the plan (correctly, per review-1 #1) now uses `--numstat --shortstat`. The plan supersedes the stale contract wording; the roadmap line should be updated to match on the next roadmap pass.

---

### Critical Issues

None.

---

### Minor / Non-blocking Notes

**A. Spell out where the stat block lands in the NUL split (Task 2 — implementation guidance).**
With the format `%x1e%H%x00%an%x00%s%x00%b%x00`, git appends the `--numstat`/`--shortstat` block *after* the trailing `%x00`. So splitting a record on `\x00` yields exactly five parts: `[sha, author, subject, body, stats_block]`, where `stats_block` is the newline-led numstat lines plus the shortstat summary. This is clean — because the body is delimited by its own NUL, a commit body containing newlines (or a line that looks like a stat line) can never leak into the file/stat parsing. The plan says "parse each record into sha, author, message, changed_files, diffstat" without naming this 5th-field structure; an implementer benefits from knowing the stat block is the tail after the 4th NUL, parsed line-by-line (numstat = `added\tdeleted\tpath`, shortstat = the ` … files changed …` line). Optional to add; the current wording is sufficient for a careful implementer.

**B. Binary files in `--numstat` (Task 2 — robustness reminder).** Binary changes render as `-\t-\tpath`. The plan's instruction to take the *path* field (3rd tab-column) already handles this correctly regardless of the `-` markers — just worth keeping in mind so the parser splits on `\t` and takes the path column rather than assuming numeric first columns.

---

### Positive Notes

- **Clean fix integration.** Every review-1 issue was addressed at the exact task it belonged to, with the verify step tightened to actually catch the previously-silent path-truncation bug (non-empty was not enough; "full, untruncated" is).
- **Correct immutability model.** `@dataclass(frozen=True, slots=True)` with `tuple[...]` fields keeps instances hashable/immutable, consistent with the py3.12 built-in-generics / `X | None` style in `src/core/config.py`.
- **NUL/RS field separation** is the right instinct for arbitrary commit-message text; live output confirms subjects/bodies (and empty bodies like `Roadmap update`) parse without breaking record shape.
- **Merge-commit handling is sound.** `git log --numstat` emits no per-file stats for merge commits by default (no `-m`), so "changed_files empty, diffstat empty, must not raise" matches real git behavior.
- **Scope discipline.** No speculative ABC, read-only subcommands only (`log`, `rev-parse`), no network, git details encapsulated behind returned domain objects — matches the architecture's seam intent.

---

### Verdict

The plan is architecturally sound, correctly scoped, and has resolved every issue from the first review. The remaining items are non-blocking drift in the roadmap/rules artifacts and optional implementation guidance. Cleared for the orchestrator.

PLAN_REVIEW_PASS
