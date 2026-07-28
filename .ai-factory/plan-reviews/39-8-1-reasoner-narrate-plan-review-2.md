## Code Review Summary

**Files Reviewed:** plan `39-8-1-reasoner-narrate.md` (revision 2) against 8 targeted source files + the governing spec `30-reasoner-narrate.md`
**Risk Level:** 🟢 Low

This is the second-round review of the plan; the first review (`…-plan-review-1.md`) raised three findings, and this revision resolves all three cleanly against ground truth:

1. **Finding 1 (wrong assumption about `_gather_context`)** — resolved. Task 4's "no neighbors" case now asserts only on the *per-neighbor* fetch and the missing "unblocks" section, and it explicitly documents that `_gather_context` always issues both the repo-scoped query and the org-wide discovery query (`reasoner.py:70,87`) for a non-None `repo`, so two knowledge calls fire even with zero neighbors. The plan now warns *not* to assert on total `fake_knowledge.calls`. Verified correct against `reasoner.py:82-116`.
2. **Finding 2 (unused import)** — resolved. Task 1 now imports only `Chunk` from `src/knowledge/store.py`, mirroring `ReasoningPromptBuilder` (`prompt.py:2`). No `KnowledgeStore` import.
3. **Finding 3 (range split robustness)** — resolved. Task 3 now uses `rsplit("..", 1)` with a two-part assert, matching how `resolver.resolve` reconstructs `f"{before}..{after}"` (`linked_change.py:60`) and surfacing a malformed range instead of mis-splitting.

Every spec clause in `30-reasoner-narrate.md` still maps to a task: query-from-both-sources (Guard §29, Task 2 step 1), shared `_gather_context` reuse with no second mechanism (Guard §28, Task 2 step 2), the narration-not-Q&A prompt (Change §16, Task 1), the commits-as-floor guarantee (Guard §33, Task 2), the eval handler as a real registered producer (Files §24, Task 3), and the two mockable guard surfaces (Verification §39-40,43, Task 4). The plan is additive — no change to `answer`/`prompt`, no DB migration, no new settings — and its file paths, imports, and constructor signatures all check out.

### Context Gates
- **Architecture (`.ai-factory/ARCHITECTURE.md` present, via CLAUDE.md):** PASS. `Reasoner` stays DI-wired at the composition root; the new `NarrationPromptBuilder` is a constructor-injected dependency with a default, and concretes remain in `scripts/eval.py`. Importing the `LinkedChange`/`CommitContext`/`Chunk`/`EpisodicEntry` public value objects continues the reasoner's established, compliant pattern (public types, never another feature's internal files).
- **Rules (`.ai-factory/RULES.md` present):** PASS. The file is intentionally empty (no project counter-defaults); no rule to violate. The plan carries no plan-layer references into code/test comments.
- **Roadmap:** PASS. Plan heading "8.1 — Reasoner narrate" matches `ROADMAP.md:83-85` (Phase 8, the broadcast projection) and its spec `30-reasoner-narrate.md`; the plan matches the spec's Change/Guards/Verification sections point-for-point, including the "commits are the floor" degradation ladder and the "single-project note when no neighbor surfaces" clause.
- **Skill-context:** no `.ai-factory/skill-context/aif-review/SKILL.md` present — no project-specific review overrides to apply.

### Critical Issues
None. Nothing blocks runtime correctness, and there is no security or migration gap (no DB schema, secrets, or external input surface touched).

### Positive Notes
- **All three prior-round findings closed with grounded reasoning**, each tied to a real line (`reasoner.py:87` for the org-wide discovery query, `prompt.py:2` for the `Chunk`-only import, `linked_change.py:60` for the range reconstruction).
- **Correct floor reasoning preserved** — the plan leans on `_gather_context`'s existing per-store/per-neighbor isolation (`reasoner.py:69-116`) and explicitly forbids a redundant try/except in `narrate`, keeping the degradation ladder in one place.
- **Composition-root reuse is right** — widening the pool-gate to fire on `narrate` and building one shared `Reasoner` for both handlers avoids a duplicate pool and construction; the `narration_prompt` default keeps the existing eval wiring valid.
- **Resolver strategy choice is verified** — the plan correctly picks `AiFactorySourceStrategy` because `roadmap_paths()` returns the real candidates (`source_strategy.py:49,56-57`) while the base/`CodeSourceStrategy` returns `()` and would starve `completed_tasks` derivation (`linked_change.py:65-70`).
- **Test discipline matches `test_reasoner_contract.py`** — asserting on `fake_embedder.calls[0]` and refusing to pin exact prompt wording or `k`. The reused `reasoner` fixture (`conftest.py:156-170`) still constructs cleanly after Task 2 adds the defaulted `narration_prompt` parameter.

Two optional polish points, neither a defect (both are behaviorally correct as written, and the codebase already accepts default-constructed prompt builders via the existing `prompt` parameter): Task 3 could pass `narration_prompt=NarrationPromptBuilder()` explicitly at the eval root to mirror the existing explicit `prompt=ReasoningPromptBuilder()` wiring, and could reuse the `collector` already built at `eval.py:153` rather than constructing a second `GitCommitCollector()` for the resolver. Implementer's discretion — the plan's current wording produces correct code either way.

## Deferred observations
- Affects: Phase 3 / user-authored eval data (`evals/cases.yaml`, `evals/reference/`) — Task 3 registers the `narrate` handler but adds no `narrate` case to `cases.yaml` and no reference note, so the harness verification stays latent until a user authors a `{repo, range, lang}` case and its reference. This is correct per the project's "references user-authored, never fabricated" rule (CLAUDE.md) and lies outside this code task's scope; noted only so the eval linkage isn't assumed live on merge. [routed → .ai-factory/specs/62-narrate-eval-case.md]

PLAN_REVIEW_PASS
