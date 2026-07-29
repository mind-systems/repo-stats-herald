# Review: 22.1 — Take the foreign product name out of the concept docs

## Scope
Documentation-only change. Two files edited; no code, no schema, no runtime surface — so there is nothing to break at runtime (no migrations, types, or races in play). Reviewed against the plan and the spec's guards.

## What changed
- `docs/concepts/derivation-modes.md`: the maturing-harness example `tradeoxy_broker` → `mind_api` (a repo of the organization's own product). The sentence still illustrates a harness maturing gradually over a repository's history.
- `docs/concepts/product-scope.md`:
  - "Why" section: the second product is now unnamed — "an unrelated platform in another domain, spanning its own repositories"; both `tradeoxy_core`/`tradeoxy_broker` repo names removed. The claim still rests on **two unrelated products** under one organization.
  - Consequence sentence: "a trading change" → "a change from that other platform"; the org-wide-retrieval blending claim still stands.
  - "Membership and dependency" section: "Two separate products (`mind`, `tradeoxy`) can share…" → "Two separate products can share…"; the pair is no longer named, and the two-products-share-a-dependency-edge point is preserved.

## Guard verification
- `grep -i tradeoxy docs/` returns no matches — the foreign product name is fully gone from the live docs.
- Only the two named files under `docs/concepts/` carry substantive edits; no other doc or spec touched.
- No `[x]` roadmap line and no completed-task spec edited; the guarded history dirs (`plans/`, `plan-reviews/`, `reviews/`, `handoffs/`) received only this task's own new orchestration artifacts, not edits to prior tasks' history.
- The second product was anonymised, not deleted and not replaced by `mind` — the two-unrelated-products argument is intact (no tautology collapse). All `mind`/`mind_*` mentions (the org's own product) correctly left in place.

## Correctness
- Both arguments in `product-scope.md` remain valid as reworded.
- `derivation-modes.md` example reads identically in intent; `mind_api` is a genuine ai-factory repo of the org's own product that matured its harness gradually — an accurate substitution.

No bugs, security, or correctness issues found.

REVIEW_PASS
