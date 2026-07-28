## Code Review Summary

**Files Reviewed:** plan `39-8-1-reasoner-narrate.md` against 6 targeted source files + the governing spec
**Risk Level:** 🟡 Medium

The plan is a faithful, well-grounded implementation of its governing spec (`.ai-factory/specs/30-reasoner-narrate.md`, named by `ROADMAP.md:85`). Every spec clause maps to a task: query-from-both-sources, shared `_gather_context` reuse, the narration prompt, the commits-as-floor guarantee, the eval handler, and the two guard-test surfaces. It is additive (no changes to `answer`/`prompt`), needs no DB migration and no new settings, and its architectural choice to encapsulate prompt text in a dedicated `NarrationPromptBuilder` matches the codebase pattern (`ReasoningPromptBuilder`, `PromptBuilder`) and the CLAUDE.md "owned details stay inside the owning class" rule. Imports, constructor signatures, and file paths all check out against ground truth. The findings below are localized corrections, not structural problems.

### Context Gates
- **Architecture (`.ai-factory/ARCHITECTURE.md` via CLAUDE.md):** PASS. `Reasoner` remains DI-wired at the composition root; the new `NarrationPromptBuilder` is injected with a default, concretes stay in `scripts/eval.py`. The reasoner already depends on the public value objects/ABCs of `episodic`/`knowledge`/`graph`; importing the `LinkedChange` value object continues that established, compliant pattern (public types, not internal files).
- **Rules (`.ai-factory/RULES.md` present):** PASS — no observed violation; the plan carries no plan-layer references into code/test comments.
- **Roadmap:** PASS. Task links to `ROADMAP.md:85` (8.1) and its spec `30-reasoner-narrate.md`; the plan matches the spec's Change/Guards/Verification sections point-for-point.

### Critical Issues
None. Nothing blocks the feature's runtime correctness or introduces a security/migration gap.

### Issues to address

1. **(Medium — wrong assumption about `_gather_context`) Task 4, "No neighbors surfaced" test — the "no neighbor query issued" clause is factually wrong.**
   `_gather_context` (reasoner.py:82–112) *always* issues an org-wide discovery query `knowledge.query(embedding, k, repo=None)` **and** a `graph.neighbors(repo)` call whenever `repo` is non-None — and `change.repo` is always a bare non-None `str`. Only the *per-neighbor* knowledge fetch is skipped when no neighbor ids surface. So a test asserting "no neighbor query issued" (e.g. checking `fake_knowledge.calls` has a single entry) would be incorrect: with zero neighbors `fake_knowledge` still receives two calls (repo-scoped + org-wide discovery). The sound assertion — and the plan's own alternative clause — is *no per-neighbor query fires and the prompt carries no "unblocks" section* (`gathered.neighbor_chunks` empty). Drop the "no neighbor query issued" phrasing so the implementer doesn't encode a false expectation.

2. **(Low — unused import) Task 1 import list names `KnowledgeStore`, but the builder needs only `Chunk`.**
   `NarrationPromptBuilder` renders chunks; it never references `KnowledgeStore` — mirroring `ReasoningPromptBuilder`, which imports only `Chunk` from `src/knowledge/store.py`. Importing `KnowledgeStore` would be an unused import and a likely ruff/lint failure. Narrow the guidance to `Chunk`.

3. **(Low — robustness, controlled data) Task 3 `inputs["range"].split("..")`.**
   Correct for the two-dot ranges eval cases use ("HEAD~3..HEAD" → `["HEAD~3", "HEAD"]`), matching how `resolver.resolve` reconstructs `f"{before}..{after}"`. A three-dot range ("a...b") would mis-split. Eval case data is author-controlled, so this is not blocking; a defensive `rsplit`/2-element check would harden it if the implementer wishes.

### Positive Notes
- **Deviation-free spec conformance grounded in real line numbers** — the plan cites `linked_change.py:21` for the bare-repo key and correctly reasons that `CodeSourceStrategy.roadmap_paths()` returns `()` (starving task derivation) so `AiFactorySourceStrategy` must supply the resolver; verified against `source_strategy.py:12-18,56-58`.
- **Correct floor reasoning** — the plan leans on `_gather_context`'s existing per-store/per-neighbor isolation (reasoner.py:69-116) and explicitly forbids adding a redundant try/except, keeping the degradation ladder in one place.
- **Composition-root reuse is right** — widening the pool-gate to fire on `narrate` and building one `Reasoner` shared across both handlers avoids a duplicate construction and a duplicate pool; the `narration_prompt` default lets the existing eval wiring stay untouched.
- **Test discipline matches `test_reasoner_contract.py`** — asserting on `fake_embedder.calls[0]` and refusing to pin exact prompt wording or `k` mirrors the established red-test convention.

## Deferred observations
- Affects: Phase 3 / user-authored eval data (`evals/cases.yaml`, `evals/reference/`) — Task 3 registers the `narrate` handler but adds no `narrate` case to `cases.yaml` and no reference note, so the harness verification is latent until a user authors a `{repo, range, lang}` case and its reference. This is correct per the project's "references user-authored (never fabricated)" rule (CLAUDE.md, `ROADMAP.md:18`) and lies outside this code task's scope — noting only so the eval linkage isn't assumed live on merge.
