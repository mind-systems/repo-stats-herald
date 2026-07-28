# Code re-review: 10.1.2 — Report sections (round 2)

Re-review after fixes for
`.ai-factory/reviews/46-10-1-2-report-sections-summary-per-branch-remaining-impl-review-1.md`.
Only `src/changelog/sections/per_branch.py` (56→68 lines) and its test
(100→123 lines) changed since round 1; all other section files, the collector,
and the prompt builder are byte-identical to the previously-reviewed state
(confirmed via `git diff --stat`).

Verification: `uv run pytest tests/changelog/` → **22 passed** (was 21; +1 for
the new dedup test).

## Per-finding verdicts

### Finding 1 (Low) — Overlapping/alias branches produce duplicate per-branch narrations → **Fixed**

`PerBranchSection.render` now dedups by resolved range before resolving or
narrating. Current `src/changelog/sections/per_branch.py:47-64`:

```python
        parts = []
        seen_ranges: set[tuple[str, str]] = set()
        for branch, branch_before, branch_after in branches:
            range_key = (branch_before, branch_after)
            if range_key in seen_ranges:
                continue
            seen_ranges.add(range_key)

            change = self._resolver.resolve(bare, branch_before, branch_after)
            if not change.commits.commits:
                # Defensive: active_branches already filters on in-window
                # commits, but a resolved range with no commits has nothing
                # for this branch to say.
                continue

            change = dataclasses.replace(change, repo=repo)
            narration = await self._reasoner.narrate(change, lang)
            parts.append(f"{_BRANCH_HEADER_TEMPLATE.format(branch=branch)}\n{narration}")
```

The class docstring documents the behavior (`per_branch.py:18-22`: "deduped by
that range so identical content is narrated (and billed to the LLM) once, under
the first branch name the collector returned it for"), and a dedicated test
pins it — `tests/changelog/test_per_branch_section.py:87-107`
(`test_branches_sharing_a_range_narrate_once_under_the_first_name`): three
branches where `main`/`staging` share `(b0, a0)` produce two sub-parts, two
`narrate` calls, and exactly two `resolver.resolve` calls, the duplicate
resolved once under `main`. Dedup happens *before* `resolve`, so the redundant
LLM call and the redundant `resolve` are both eliminated. Correct — a shared
range yields an identical `LinkedChange`, so no information is lost by collapsing
it. Verdict: **Fixed.**

### Finding 2 (Low / deferred to 10.2) — `active_branches` raises on a non-commit `before`/`after` → **Not fixed (accepted deferral, unchanged by design)**

`src/commits/collector.py:148-149` is unchanged:

```python
        before_time = self.commit_timestamp(repo_path, before).isoformat()
        after_time = self.commit_timestamp(repo_path, after).isoformat()
```

`commit_timestamp` (`collector.py:196-203`) still runs with `check=True` and
`datetime.fromisoformat(...)`, so a non-commit `before`/`after` (e.g. an
`EMPTY_TREE_SHA` lower bound from a future `TimeWindow`) would raise rather than
degrade. This was classified Low and explicitly deferred in round 1: it is not
reachable from any current caller (`TimeWindow` is unbuilt; nothing passes
empty-tree here), and the method's docstring (`collector.py:141-146`) documents
`before`/`after` as caller-resolved valid refs. It remains an out-of-scope
heads-up for 10.2's `TimeWindow`, not a defect in this changeset. No action
required in this task.

## New issues

None. The dedup change is self-contained, introduces no new control-flow or
type risk, correctly orders the dedup ahead of both `resolve` and `narrate`,
and preserves stable output order (first-name-wins). The full suite remains
green (138 passing across the project at round 1; the changelog subset is 22).

The one carried-forward item (Finding 2) is an explicitly-deferred 10.2
concern, not an in-scope actionable defect for 10.1.2.

REVIEW_PASS
