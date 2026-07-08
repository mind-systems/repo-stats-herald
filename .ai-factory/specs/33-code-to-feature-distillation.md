# 5.2.2 — Code-to-feature distillation (impl)

**Phase:** 5 — Code-derived understanding. Depends on 5.2.1 (the `CodeDistiller` signature and its bounded-unit grouping/composition tests). Second half of the distiller milestone — turns 5.2.1's grouping tests green and adds the real LLM-prompting logic.

## Current state

5.2.1 defines `CodeDistiller.distill`'s signature and pins the bounded-unit grouping/composition mechanics with red tests over a mocked `LLMClient`. No real prompting exists yet — embedding raw code directly would surface *similar code*, not *related features* — the exact failure the meaning layer exists to avoid (see `docs/concepts/code-derived-understanding.md`).

## Change

Implement the real per-unit distillation: read each bounded unit's code from the mirror and prompt the LLM for feature-level description, using 5.2.1's grouping/composition mechanics unchanged.

- `src/knowledge/code_distiller.py` — `CodeDistiller.distill`: for each bounded unit produced by 5.2.1's grouping, read the unit's code from the mirror and prompt the `LLMClient` (Phase 1's boundary — not the reasoner, Phase 7, which reasons over an already-distilled memory) to describe **what it does at the feature level**: delivered behavior and purpose, never a class/method/call-chain listing; compose the per-unit descriptions via 5.2.1's composition logic, unchanged.

## Files & types

- edit `src/knowledge/code_distiller.py` (stub → real per-unit prompting, greening 5.2.1's tests)

## Guards

- Output is **delivered-value features**, never a symbol dump — the prompt explicitly steers away from "class X has methods Y, Z."
- Model-agnostic — goes through `LLMClient` (Phase 1), not a hardcoded backend.
- **Bounded units** — reuses 5.2.1's grouping unchanged; this task does not re-decide how paths are partitioned.
- Turns 5.2.1's tests green — introduces no new grouping/composition behavior beyond what 5.2.1 already pinned.

## Verification

- 5.2.1's grouping/composition test suite passes green against this implementation (with the real `LLMClient` swapped in for the mock).
- Run through **the eval harness** (Phase 1's `evals/`): on a real code-only repo (Tradeoxy), the distilled feature model is diffed against a **user-authored** reference feature description (never fabricated — same discipline as the summarization eval) and names features, not classes.
