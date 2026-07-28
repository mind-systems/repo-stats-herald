# Architect buffer — deferred-observations resolution

## Resolved

- **Routing-target fork.** Four phases (18–21) outlined above `---STOP---` and fully
  decomposed: twelve open task specs, `53`–`64`. Every live gap now has a legal
  `[routed → …]` address. Phase 13 stays deployment packaging.
- **Doc-edit permission.** The user ruled `CLAUDE.md` and `docs/` are the governing spec
  and are editable — a doc-layer fix is a legitimate disposition.
- **Manual-task convention.** No precedent existed in this roadmap. Introduced for 21.2:
  `(manual)` in the task name plus the prohibition as the opening words of both the
  contract line's description and the spec body, ahead of `## Current state`.

## Open

- **All 76 entries are still unpinned** — the prune stays blocked. Addresses now exist,
  so the marker round is unblocked.
  *Trigger:* the user's go.

- **No `[fixed]` is honest this session.** Nothing was changed in `src/` or `tests/`, so
  every cluster resolves to `[routed → <spec>]` or `[dismissed]`. Do not reach for
  `[fixed]` to make a cluster look closed.

- **Three clusters verified closed in code; dismissal not yet written.** C6 (token via
  `GIT_CONFIG_*` env, `mirror.py:188-203`), C8 (`sweep_worktrees()` wired at four roots),
  C14 (`except UnicodeDecodeError` in `indexer.py`). Dismissed on evidence, not on
  reviewer prose.
  *Trigger:* the marker round.

- **Handoff §11 is short by one file and §10's fourth worked example is wrong.**
  `reviews/47-10-2-report-schedules-delivery-review-1.md` (3 entries, :17/:19/:21) is
  absent — true population 76/59, not 73/34. §10's "cross-path roadmap move" example
  conflates two distinct defects that §11 itself keeps apart. Correct the handoff once,
  after dispositions are settled.
  *Trigger:* dispositions agreed.

- **`getattr(plan, "changelog_base_url", None)` vs. the 12.1 contract.** Not one of the
  76; surfaced while reading `_deliver_release`. Task 20.1 preserves it verbatim and
  explicitly does not resolve it. Needs its own decision.
  *Trigger:* raise once the marker round is done.
