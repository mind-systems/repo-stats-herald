# Plan: 10.1.2 — Report sections: summary, per-branch, remaining (impl)

## Context
Green 10.1.1's stubbed composition with three real `ReportSection` implementations — `SummarySection` (holistic shipped story), `PerBranchSection` (per-branch who-did-what), `RemainingSection` (what's still open) — each a self-contained content block over an already-resolved `(before, after)` range on the ensured bare mirror.

## Settings
- Testing: yes (mandatory per spec — see Phase 3)
- Logging: minimal
- Docs: no

## Key design decisions (ground-truth checks before coding)

- **`repo` at `render(...)` is the bare repo KEY, not a filesystem path.** 10.2's entrypoint iterates `served_repos` (bare keys like `owner/name`), calls `mirror.ensure(repo, org_id)`, then `Report.build(repo, org_id)`. Sections therefore translate the key to the bare object-store path with `RepoMirror.object_store_path(repo)` (already-ensured precondition owned by the caller — sections never call `mirror.ensure`), and run all git ops against that path. This mirrors `src/episodic/backfill.py` (`bare = str(self._mirror.object_store_path(repo))`).
- **`LinkedChange.repo` must carry the bare KEY when handed to `Reasoner.narrate`.** `LinkedChangeResolver.resolve(bare, before, after)` runs `git -C bare` and stores that same `bare` path as `LinkedChange.repo`. But `Reasoner.narrate` (src/reasoning/reasoner.py:150) scopes `_gather_context(query, change.repo)` — and the knowledge/episodic stores are keyed by the bare repo KEY. Passing the filesystem path scopes retrieval to a key with zero rows, silently degrading the summary to a commits-only digest and dropping the cross-project "unblocks" reach (7.2) that is the whole point of `SummarySection`. **Fix:** after resolving, rebind the key with `dataclasses.replace(change, repo=repo)` before calling `narrate`. Do **not** change `LinkedChangeResolver.resolve`'s signature (outside this task's file list; `backfill` relies on current behavior).
- **`narrate_report` does not exist in the code** — only `Reasoner.narrate` (reasoner.py:137). The spec's "retire `narrate_report`" is already true on the ground. Task 6 records this as a DEVIATION and makes no edit to `reasoner.py` beyond confirming absence; sections call `narrate` directly.
- **Dependency direction:** `changelog` imports from `reasoning`, `llm`, `commits`, `github` (mirror), and `knowledge` (source strategy) — never the reverse. All injected as abstractions/infra via constructor; concretes are wired only at the (future 10.2) composition root.

## Tasks

### Phase 1: Shared git + parse helpers

- [x] **Task 1: Active-branch enumeration on the bare mirror**
  Files: `src/commits/collector.py`
  Add a read-only, no-raise method to `GitCommitCollector` that, given the canonical `(before, after)` SHA range, derives the window's **time boundary** from the two commit dates and returns one `(branch, branch_before, branch_after)` triple per branch active in that span. Mirror the existing helpers' style (`subprocess.run(..., check=False)`, `returncode != 0 → []`/skip, `--end-of-options`, `EMPTY_TREE_SHA` for a missing lower bound):
    - `before_time`/`after_time` via the existing `commit_timestamp` (`git show -s --format=%cI`).
    - Enumerate branches: `git for-each-ref --format=%(refname:short) refs/heads/`.
    - For each branch, list in-window commits: `git rev-list --since=<before_time> --until=<after_time> <branch>` (newest-first). Empty → branch inactive, skip it.
    - `branch_after` = the newest in-window SHA (first line above); `branch_before` = `git rev-list -1 --until=<before_time> <branch>`, falling back to `EMPTY_TREE_SHA` when the branch has no commit at/before `before_time`.
  Return a `list[tuple[str, str, str]]` (or a small frozen `BranchRange` value object in `src/commits/models.py` if it reads cleaner). Verify the `--since` boundary excludes the `before` commit itself and `--until` includes `after`. This is git plumbing the section tests mock away; keep exact-flag correctness self-contained here.
  DEVIATION: plan said `--since=<before_time>` excludes the `before` commit itself / ground truth (verified against a real repo: `git rev-list --since=<X> ... ` where a commit is dated exactly `X`) shows `--since`/`--until` are both inclusive of a commit dated exactly at the boundary instant, i.e. `[before_time, after_time]` is closed on both ends, not half-open / done: implemented and documented as the closed interval it actually is; correctness is unaffected because `branch_before` is derived independently via its own `rev-list -1 --until=<before_time>` query (not by filtering the `--since` list), so a branch whose only in-window commit sits exactly at `before_time` yields `branch_before == branch_after` — an empty two-dot range that `PerBranchSection`'s defensive empty-commits check (Task 4) already skips.

- [x] **Task 2: Open-task `[ ]` roadmap parse + remaining framing prompt**
  Files: `src/changelog/sections/remaining.py` (new — parse helper only in this task), `src/reasoning/remaining_prompt.py` (new)
  - In `remaining.py`, add a pure module-level function `open_tasks(content: str) -> list[str]` that returns the text of each open roadmap task line. Mirror `src/episodic/linked_change.py`'s regex approach but for the **unchecked** box: `re.compile(r"^\s*[-*]\s*\[\s\]")` — match `- [ ]`/`* [ ]` only, **never** `[x]`/`[X]`, and never via retrieval. Capture the task text following the checkbox (e.g. the `**N.N — subject**` portion or the remainder of the line) for framing. Keep the checked-line regex distinct from the open-line regex — do not reuse `_DONE_LINE_RE`'s semantics.
  - In `remaining_prompt.py`, add `RemainingPromptBuilder` owning the prose-framing prompt text ("here are the tasks still open at the report's end — frame them for readers", in the requested `lang`). Encapsulate the prompt string in the builder (project pattern: prompt text lives in a builder, not inline in the caller). Living in `src/reasoning/` keeps all LLM-prompt builders together; `changelog` importing it is the allowed one-way direction. This is the residual framing primitive the spec permits — it lives only for `RemainingSection`, not as a second `Reasoner` summary sibling.

### Phase 2: Section implementations

- [x] **Task 3: `SummarySection` — holistic shipped story** (depends on the key-rebind decision above)
  Files: `src/changelog/sections/summary.py` (new), `src/changelog/sections/__init__.py` (new)
  `SummarySection(ReportSection)` with constructor DI: `RepoMirror`, `LinkedChangeResolver`, `Reasoner`. In `render(repo, org_id, before, after, lang="ru")`:
    - `bare = str(mirror.object_store_path(repo))`.
    - `change = resolver.resolve(bare, before, after)`.
    - **Empty window → `None` before any LLM call:** if `not change.commits.commits`, return `None` (do not call `narrate`).
    - Otherwise `change = dataclasses.replace(change, repo=repo)` to scope narration to the bare KEY, then `return await reasoner.narrate(change, lang)`.
  It does **not** read open tasks (that is `RemainingSection`'s job). Cross-project "unblocks" comes from the reasoner's own reach (7.2) inside `narrate` — no separate neighbor/narrator path.

- [x] **Task 4: `PerBranchSection` — per-branch who-did-what** (depends on Task 1)
  Files: `src/changelog/sections/per_branch.py` (new)
  `PerBranchSection(ReportSection)` with constructor DI: `RepoMirror`, `GitCommitCollector`, `LinkedChangeResolver`, `Reasoner`. In `render(...)`:
    - `bare = str(mirror.object_store_path(repo))`.
    - `branches = collector.<active-branch method from Task 1>(bare, before, after)`.
    - No active branch → `None`.
    - For each `(branch, branch_before, branch_after)`: `change = resolver.resolve(bare, branch_before, branch_after)`; skip a branch whose resolved change has no commits (defensive); `change = dataclasses.replace(change, repo=repo)`; `part = await reasoner.narrate(change, lang)`. Emit one labelled sub-part per branch (a branch header line, e.g. `### <branch>`, above its narration).
    - Join the sub-parts with `"\n\n"`; if none survived, `None`.
  Iterate branches in the collector's returned order (deterministic) so output order is stable.

- [x] **Task 5: `RemainingSection` — what remains open** (depends on Task 2)
  Files: `src/changelog/sections/remaining.py`
  Add `RemainingSection(ReportSection)` to the file that already holds `open_tasks`. Constructor DI: `RepoMirror`, `GitCommitCollector`, `SourceStrategy`, `LLMClient`, `RemainingPromptBuilder`. In `render(repo, org_id, before, after, lang="ru")`:
    - `bare = str(mirror.object_store_path(repo))`.
    - Read the roadmap at the window's end commit **`after`** (the report's "now", not literal repo HEAD): iterate `source_strategy.roadmap_paths()` and take the first that `collector.read_blob(bare, after, path)` returns non-`None` (mirror `_read_roadmap_versions` in linked_change.py). No roadmap present → `None`.
    - `tasks = open_tasks(content)`; no open tasks → `None` (return **before** any LLM call).
    - Otherwise `return await llm.generate(prompt.build(tasks, lang))`.

- [x] **Task 6: Confirm `narrate_report` retirement + pin section registry keys** (depends on Tasks 3–5)
  Files: `src/reasoning/reasoner.py` (verify only), `src/changelog/sections/__init__.py`
  - DEVIATION: plan/roadmap said "edit `reasoner.py` — retire `narrate_report`"; ground truth shows no `narrate_report` exists (only `narrate`). No edit to `reasoner.py`; confirm sections call `narrate` directly and record the deviation.
  - Add a composition helper `default_section_registry(mirror, resolver, reasoner, collector, source_strategy, llm, remaining_prompt) -> dict[str, ReportSection]` returning the three sections under their canonical keys `"summary"`, `"per_branch"`, `"remaining"` (the keys `Report`/`report_for_schedule` look up). This receives already-built deps and is invoked by 10.2's composition root — it pins the key↔section mapping in one home so a schedule config key can't silently drift. Do **not** build a composition root or `scripts/report.py` here (that is 10.2).

### Phase 3: Mandatory tests

- [x] **Task 7: Section unit tests (mocked mirror / git / source strategy / reasoner)** (depends on Tasks 3–5)
  Files: `tests/changelog/test_summary_section.py` (new), `tests/changelog/test_per_branch_section.py` (new), `tests/changelog/test_remaining_section.py` (new)
  Follow the existing `tests/changelog/` style (async tests, fake collaborators over real git). Mock the mirror (`object_store_path` → a fixed path), the collector/resolver, the reasoner (`narrate`), the source strategy, and the LLM.
    - **`SummarySection`:** empty window (resolver returns a `LinkedChange` with no commits) → `None` **and** `reasoner.narrate` is never awaited; non-empty → `narrate` awaited exactly once with a change whose `.repo` equals the passed bare **KEY** (assert the `dataclasses.replace` rebind); does not read open tasks.
    - **`PerBranchSection`:** an inactive branch (not returned by the active-branch method) is skipped; N active branches → N labelled sub-parts, order preserved; none active → `None`.
    - **`RemainingSection`:** exact `[ ]`-parse — given roadmap content mixing `[x]`/`[X]` and `[ ]` lines, only the `[ ]` lines frame (never `[x]`, never retrieval); no open `[ ]` tasks → `None` with the LLM never called.
  LLM prose quality is out of scope for unit tests — it is verified through the eval harness against user-authored references once the report is wired (10.2); the `narrate` path already has an eval handler (8.1). Do not fabricate eval references here.
