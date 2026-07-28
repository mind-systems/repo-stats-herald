# Plan Review: 10.1.2 — Report sections (summary, per-branch, remaining) impl

**Plan reviewed:** `.ai-factory/plans/46-10-1-2-report-sections-summary-per-branch-remaining-impl.md`
**Governing spec:** `.ai-factory/specs/17-weekly-digest-builder.md` (via ROADMAP line 100)
**Risk Level:** 🟢 Low

## Context Gates

- **Architecture (`.ai-factory/ARCHITECTURE.md`):** PASS. Feature-modular + constructor DI. Every section receives abstractions (`RepoMirror`, `LinkedChangeResolver`, `Reasoner`, `GitCommitCollector`, `SourceStrategy`, `LLMClient`, `RemainingPromptBuilder`) via constructor; concretes wired only at the future 10.2 composition root. The `changelog → reasoning` dependency is one-way and matches the existing precedent (`changelog` already depends on `reasoning`'s public classes). No feature reaches into another's internals. WARN (non-blocking) noted below on prompt-builder placement.
- **Rules (`.ai-factory/RULES.md`):** PASS. File is intentionally empty (no project counter-defaults); nothing to violate.
- **Roadmap (`.ai-factory/ROADMAP.md` line 100):** PASS. Plan tasks map cleanly onto the contract line: three `ReportSection` impls, `narrate_report` retirement, mirror-only reads, `changelog→reasoning` one-way, and the three mandated test shapes (PerBranch enumeration, Remaining exact `[ ]`-parse, Summary empty→`None`).
- **Spec (`17-weekly-digest-builder.md`):** PASS. The three sections, the time-boundary derivation for per-branch, the `after`-commit roadmap read for remaining, the "no separate narrator path" guard, and "residual framing primitive lives only in `RemainingSection`" are all honored.

## Ground-truth verification (assumptions checked against code)

Every codebase assumption in the plan was verified against the actual files:

- ✅ `RepoMirror.object_store_path(repo)` returns the bare KEY→path (mirror.py:56); `bare = str(mirror.object_store_path(repo))` matches `backfill.py:71` exactly.
- ✅ The mirror is created with `git clone --mirror` (mirror.py:114) — so `git for-each-ref refs/heads/` in Task 1 genuinely enumerates every mirrored branch. The branch-enumeration approach is valid against a bare mirror.
- ✅ `LinkedChangeResolver.resolve(repo, before, after)` stores its `repo` argument (the bare path) as `LinkedChange.repo` (linked_change.py:62). The key-rebind concern is real: `Reasoner.narrate` scopes `_gather_context(query, change.repo)` (reasoner.py:150), and the knowledge/episodic stores are keyed by the bare KEY, not the fs path. Without the `dataclasses.replace(change, repo=repo)` rebind, retrieval would silently scope to a zero-row key and drop cross-project reach. The fix is correct and the "don't change `resolve`'s signature" caveat correctly protects `backfill`.
- ✅ `LinkedChange` is `@dataclass(frozen=True, slots=True)` — `dataclasses.replace` works with frozen+slots.
- ✅ `narrate_report` does not exist anywhere in `src/` (only `Reasoner.narrate`, reasoner.py:137). The DEVIATION in Task 6 (record absence, no edit to `reasoner.py`) is the correct handling of the spec's "retire `narrate_report`" line.
- ✅ `GitCommitCollector` helper style matches Task 1's prescription: `subprocess.run(..., check=False)`, `returncode != 0 → []`, `--end-of-options`, `EMPTY_TREE_SHA`, and `commit_timestamp` via `git show -s --format=%cI`.
- ✅ `read_blob(bare, ref, path)` returns content or `None` (collector.py:104) — RemainingSection's "first roadmap path that is non-`None` at `after`" mirrors `_read_roadmap_versions`.
- ✅ `SourceStrategy.roadmap_paths()` returns candidate paths in priority order (source_strategy.py); `AiFactorySourceStrategy` returns `("ROADMAP.md", ".ai-factory/ROADMAP.md")`.
- ✅ `LLMClient.generate(prompt) -> str` (client.py:8) — RemainingSection's `llm.generate(prompt.build(tasks, lang))` matches.
- ✅ `_DONE_LINE_RE = r"^\s*[-*]\s*\[[xX]\]"` (linked_change.py:12); Task 2's open-line regex `r"^\s*[-*]\s*\[\s\]"` is correctly kept distinct and never reuses done-line semantics.
- ✅ `ReportSection.render(repo, org_id, before, after, lang="ru")` signature (section.py) — all three sections conform; `org_id` unused by these sections is fine (mirror.ensure is the caller's job, per the ABC docstring).
- ✅ Test conftest (`tests/changelog/conftest.py`) uses async fakes over real git — Task 7's mocked-collaborator style is consistent.

## Critical Issues

None.

## Positive Notes

- The two hardest correctness traps are identified and pinned up front in "Key design decisions": the KEY-vs-path rebind before `narrate`, and the fact that a single canonical `(before, after)` range names no other branch's commits (hence the time-boundary derivation). Both are grounded with file:line references.
- The empty-window / no-active-branch / no-open-task early returns are consistently placed **before** any LLM call, and Task 7 asserts the "reasoner/LLM never awaited" contract — matching the spec's "empty → `None` before any LLM call."
- Task 1 correctly isolates the exact-flag git plumbing (the `--since` exclusive / `--until` inclusive boundary) as self-contained and self-verified, since the section tests mock it away — this is the right seam to keep the fiddly correctness local.
- Task 6 pins the `summary`/`per_branch`/`remaining` registry keys in one home so a schedule-config key cannot silently drift from the section it names, and correctly defers the composition root / `scripts/report.py` to 10.2.
- Scope discipline is clean: no composition root, no `TimeWindow.resolve` implementation, no eval references fabricated — all correctly left to their owning phases.

## Non-blocking consideration (not a finding)

- **`RemainingPromptBuilder` home (`src/reasoning/remaining_prompt.py`).** This is the one placement that is arguable rather than clearly correct. ARCHITECTURE guardrail #6 ("prompt text stays inside the class that owns it") would point to the changelog side, since `RemainingSection` is the sole consumer and `Reasoner` never touches this prompt. The plan's counter-rationale — keep all LLM-prompt builders co-located in `reasoning`, alongside `NarrationPromptBuilder`/`ReasoningPromptBuilder`, and inject across the already-allowed `changelog→reasoning` edge via constructor — is coherent and consistent with the existing module, and the builder is DI'd (not reached into). Either home satisfies the DI and one-way-dependency rules. Flagging only so the implementer makes the placement deliberately; it does not block the plan. If the implementer instead colocates it in `src/changelog/`, keep it a public class injected at the root, not inline in `RemainingSection`.

PLAN_REVIEW_PASS
