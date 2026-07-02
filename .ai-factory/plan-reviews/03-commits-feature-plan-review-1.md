# Plan Review: commits/ feature (03-commits-feature.md)

## Code Review Summary

**Files Reviewed:** plan (3 tasks) + targeted codebase (`src/core/config.py`, `src/__init__.py`, `src/core/__init__.py`, `ARCHITECTURE.md`, `ROADMAP.md`, `.ai-factory/rules/base.md`, spec note `03-commits-feature.md`, live `git log` behavior on this repo)
**Risk Level:** 🟡 Medium

The plan is well-aligned with the spec note, the roadmap task, and the feature-modular architecture. Package layout, immutability choices, DI stance, and the "no ABC yet" decision are all correct. One implementation choice in the git-parsing strategy will silently produce **wrong** `changed_files` data, and a couple of smaller parsing/hardening details need tightening. None are architectural — all are contained within Tasks 2–3.

---

### Context Gates

- **Architecture (`ARCHITECTURE.md`)** — ✅ PASS. Plan follows feature-modular layout: `src/commits/` owns its own `models.py` + `collector.py`, no root-level `models/` dump. `GitCommitCollector` is a plain class returning domain objects (the swappable seam for a future `GitHubCommitCollector`). Deferring the `Collector` ABC matches principle #4 ("introduce an ABC when a real second implementation is imminent — not speculatively").
- **Rules (`.ai-factory/rules/base.md`)** — ⚠️ WARN (non-blocking). `base.md` still describes a layer-first structure (`src/routes/`, `src/services/`, `src/models/`) that contradicts the feature-modular `ARCHITECTURE.md`. The plan correctly follows `ARCHITECTURE.md` (the more specific, newer contract), not this stale rule. No action needed in this plan; the `rules/base.md` module-structure section is drift that should be reconciled with the architecture doc separately.
- **Roadmap (`ROADMAP.md`)** — ✅ PASS. Maps exactly to the active task "**commits/ feature**" (Phase 1): `models.py` (immutable `Commit`, `CommitContext`) + `collector.py` (`GitCommitCollector.collect(repo_path, rev_range)`), read-only `git log`, local git only, empty-range/merge-commit guards, `HEAD~3..HEAD` verify. Full linkage present.

---

### Critical / High-Priority Issues

**1. `--stat` truncates file paths → `changed_files` will contain wrong paths (Task 2)**

Task 2 derives *both* `changed_files` and the `diffstat` summary from `git log ... --stat`. I ran the exact command from the plan on this repo:

```
$ git log HEAD~3..HEAD --stat --pretty=format:'%x1e%H%x00%an%x00%s%x00%b%x00'
 ...
 .../02-settings-layer-plan-review-1.md   | 40 ++++++
 .ai-factory/plans/02-settings-layer.md   | 34 ++++++
```

`--stat` **abbreviates long paths with a leading `...`** and column-truncates to terminal width. The real path `.ai-factory/plan-reviews/02-settings-layer-plan-review-1.md` comes out as `.../02-settings-layer-plan-review-1.md`. So `changed_files` would be populated with **truncated, non-real paths** — data that looks fine but is wrong, and useless to the downstream summarizer which is supposed to reason over actual changed paths.

The verify step ("`changed_files` … non-empty") does **not** catch this: truncated strings are still non-empty, so the manual check passes while the data is subtly corrupt.

**Fix:** separate the two concerns and use machine-readable git output:
- File list → `--numstat` (full, unabbreviated, tab-separated paths, never truncated).
- Summary line → `--shortstat` (emits exactly `N files changed, X insertions(+), Y deletions(-)`).

Both can be requested together. Verified on this repo:

```
$ git log HEAD~3..HEAD --numstat --shortstat --pretty=format:'%x1e%H%x00%an%x00%s%x00%b%x00'
1	1	.ai-factory/ROADMAP.md
40	0	.ai-factory/plan-reviews/02-settings-layer-plan-review-1.md   ← full path
...
 11 files changed, 212 insertions(+), 2 deletions(-)                ← clean summary
```

Recommend updating Task 2 to specify `--numstat --shortstat` (parse the `added\tdeleted\tpath` lines for `changed_files`, the ` N files changed…` line for `diffstat`) instead of `--stat`. Add a note for renames: `--numstat` renders them as `old => new` unless `-z` is used, where the two paths become separate NUL-terminated fields — pick one and parse it explicitly.

---

### Medium / Minor Issues

**2. Leading empty record, not trailing (Task 3)**

The format prefixes each record with the record separator (`%x1e%H…`), so the output starts with `\x1e`. Splitting on `\x1e` yields an **empty leading element** (`['', rec1, rec2, …]`) — confirmed in the live output (`^^<sha>` at the very start). Task 3 only says "ignore empty **trailing** records from the split." An implementer following that literally may still index `[0]` and hit the empty leading record. **Fix:** phrase the guard as "drop empty records regardless of position" (e.g. filter out any record that is empty/whitespace after strip), which covers both leading and trailing.

**3. Options-injection via `rev_range` (Task 2/3, low severity — hardening)**

`rev_range` is passed as a positional argument to `git log`. A value beginning with `-` (e.g. `--output=…`, `--all`) would be parsed by git as an *option*, not a revision. Input is trusted (config-driven, not end-user) so risk is low, but since the plan's own guard is "only read-only subcommands, never mutate/network," it's worth hardening: pass `--end-of-options` before `rev_range` (or validate that `rev_range` doesn't start with `-`). Keep using `subprocess.run` with an **argument list (no `shell=True`)** — the plan implies this via `capture_output=True`; make it explicit so no shell interpolation is possible.

**4. `check=True` vs. the empty-range guard (Tasks 2 vs 3 — consistency)**

Task 2 specifies `subprocess.run(..., check=True)`. An empty revision range (Task 3's first guard) is fine — `git log` with a valid-but-empty range exits 0 with empty output, so parsing yields an empty `commits` tuple naturally. But an *invalid/unknown* range makes `git log` exit non-zero, and `check=True` will raise `CalledProcessError`. That's acceptable (fail loud on a bad range), but the plan should state the intended behavior explicitly so "never crashes" (Task 3) isn't read as "swallow bad-range errors." Clarify: empty range → empty context; malformed/unknown range → propagate the error.

---

### Positive Notes

- **Correct immutability model.** `@dataclass(frozen=True, slots=True)` with `tuple[...]` fields keeps instances hashable/immutable — the right call for value objects, and consistent with the py3.12+ built-in-generics style already in `src/core/config.py`.
- **NUL/RS field separation** is the right instinct for parsing arbitrary commit-message text; the live test confirms subjects/bodies parse cleanly and empty bodies (`Roadmap update`) don't break the record shape.
- **Merge-commit handling is sound.** `git log --stat/--numstat` emits no per-file stats for merge commits by default (no `-m`), so Task 3's "changed_files empty, diffstat empty, must not raise" matches real git behavior — verified.
- **Package marker** matches the existing pattern (`src/__init__.py` and `src/core/__init__.py` are both empty 0-byte files).
- **Scope discipline** is good: no speculative ABC, no network, read-only subcommands only, clean encapsulation of git details behind the returned domain objects.

---

### Verdict

The plan is architecturally sound and correctly scoped, but Issue **#1** (`--stat` path truncation) will produce silently-wrong `changed_files` and should be fixed before implementation by switching the file-list source to `--numstat --shortstat`. Issues #2–#4 are minor parsing/robustness clarifications. Recommend addressing #1 (and ideally #2) in the plan before it goes to the orchestrator.
