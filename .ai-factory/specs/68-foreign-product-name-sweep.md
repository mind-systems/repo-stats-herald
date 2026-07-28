# 22.1 — Take the foreign product name out of the concept docs

**Phase:** 22 — A live doc names no foreign product. Touches only two files under `docs/concepts/`; independent of every other open task.

## Current state

Four mentions across two documents. In `docs/concepts/product-scope.md`, the "Why" section builds its central claim — that an organization is not a product — on one organization holding two unrelated products, and names both to make the point; a later passage, separating membership from dependency, names the same pair again as an example of two products sharing a dependency edge. In `docs/concepts/derivation-modes.md`, one sentence illustrates a harness maturing gradually over a repository's history by citing a repository that belongs to the foreign product. Open task specs and open roadmap lines were checked and carry no such reference — the whole live surface needing this change is these two documents.

## Change

In `product-scope.md`, keep both arguments intact and render the second product unnamed in each — an unrelated platform within the same organization, described by what it is rather than by its name; the membership-versus-dependency passage makes the same point without naming the pair. In `derivation-modes.md`, move the example to a repository of this organization's own product whose harness likewise matured gradually over its own history.

## Files & types

- edit `docs/concepts/product-scope.md`
- edit `docs/concepts/derivation-modes.md`

## Guards

- Every argument must still stand as written: the scope document's claim depends specifically on there being two *unrelated* products under one organization, so the second one is anonymised — described, never deleted, and never replaced by the very product it is being contrasted against, which would collapse the argument into a tautology.
- No history is edited: nothing under `.ai-factory/plans/`, `plan-reviews/`, `reviews/`, or `handoffs/`; no spec of a completed task; no `[x]` roadmap line.
- The change is confined to the two named files under `docs/concepts/`.

## Verification

- Neither document names the foreign product.
- `product-scope.md` still argues that an organization is not a product, and still shows two products sharing a dependency edge.
- `derivation-modes.md` still illustrates a harness maturing gradually over its history.
- A search of live artifacts returns no mention of the foreign product, while the historical record is unchanged.
