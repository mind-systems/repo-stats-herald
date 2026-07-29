# Plan: 22.1 — Take the foreign product name out of the concept docs

## Context
Two forward-looking concept docs name a foreign product (`tradeoxy`, the trading platform under the `mind-systems` organization); this task strips those four mentions while keeping every argument intact — the scope doc's second product becomes an unnamed unrelated platform, and the derivation doc's example moves to a repository of the organization's own product (`mind`).

## Settings
- Testing: no
- Logging: minimal
- Docs: no

## Tasks

### Phase 1: Concept-doc edits

- [x] **Task 1: Anonymise the second product in `product-scope.md`**
  Files: `docs/concepts/product-scope.md`
  Remove all `tradeoxy` mentions while preserving both arguments verbatim in force.
  - In the "Why" section (currently: "two unrelated products — a health platform across seven repositories (`mind_api`, `mind_mcp`, `mind_mobile`, `mind_web`, …) and a trading platform across four (`tradeoxy_core`, `tradeoxy_broker`, …)"): keep the health platform named (it is the organization's own product), but render the second product **unnamed** — describe it by what it is (an unrelated platform in another domain under the same organization, spanning its own repositories) with **no product name and no repo names** (`tradeoxy_core`/`tradeoxy_broker` must go). The claim "an organization is not a product" must still rest on there being **two unrelated products** under one organization.
  - In the same section's consequence sentence ("would blend a trading change into a health project's context"): reword so the blended change belongs to the unnamed unrelated product, not a named "trading" one, so the org-wide-retrieval claim still stands.
  - In the "Membership and dependency are two relations" section (currently: "Two separate products (`mind`, `tradeoxy`) can share such an edge without being one product."): make the same point **without naming the pair** — e.g. "Two separate products can share such an edge without being one product."
  - Leave every `mind`/`mind_*` mention untouched — those name the organization's own product and are in scope to keep.
  - Guard: do not replace the second product with `mind` (the product it is contrasted against) — that would collapse the argument into a tautology.

- [x] **Task 2: Move the maturing-harness example to the org's own product in `derivation-modes.md`**
  Files: `docs/concepts/derivation-modes.md`
  In the sentence "Every ai-factory repo predates its own `.ai-factory/`; `tradeoxy_broker` grew its docs gradually.", replace `tradeoxy_broker` with a repository of the organization's own product whose harness likewise matured gradually (e.g. `mind_api`). The illustration — a harness maturing gradually over a repository's history — must read exactly as before, only with a non-foreign repo name.
