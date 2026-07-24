# Coordination-Root Format

A **coordination root** is a repository whose `CLAUDE.md` declares the members of a product and
the contracts between them. Herald reads that declaration from the canonical ref and materializes
it as precise [project-graph](understanding.md#project-graph) edges — the authoritative complement
to what retrieval infers. This page is the format contract: a repository that adopts it opts into
automatic, versioned management of its product's edges.

## Recognition

A repository is a coordination root when its `CLAUDE.md` carries a `## Coordination` section. That
section is the declaration; a `CLAUDE.md` without it is an ordinary file and seeds nothing. Only the
`## Coordination` section is read — every other heading, table, and paragraph in the file is ignored,
so a coordination root's `CLAUDE.md` may also hold a Commands table, a docs index, or any other
tables without polluting the graph.

## The member table

The `## Coordination` section holds one Markdown table with a fixed header:

```markdown
## Coordination

| Member  | Relationship             |
|---------|--------------------------|
| api     | contract: payments.proto |
| auth    | auth                     |
| mobile  | dependency               |
```

| Column | Meaning |
|--------|---------|
| **Member** | the sub-project's repository name exactly as GitHub sends it in a push (`push.repo` — bare, no org prefix). Both endpoints of every seeded edge use this bare form, so an edge resolves against the same identity a push carries. |
| **Relationship** | the tie from the coordination root to that member, classified into one edge kind (below). |

The header row and the separator row are not members, and a row with an empty Member cell is skipped.

## Edge kinds

The first word of the Relationship cell selects the [edge kind](understanding.md#project-graph);
anything after it is descriptive detail:

| Relationship cell | Kind |
|-------------------|------|
| `contract` (optionally `contract: <artifact>`) | `CONTRACT` |
| `auth` | `AUTH` |
| anything else, or plain membership text | `DEPENDENCY` |

Each row becomes one directed edge `root → member` of that kind, tagged `source=seed`.

## Lifecycle — versioned and automatic

The table is the current authoritative structure, re-read on every canonical-ref push and on backfill:

- Adding a member row adds its edge; removing a row removes it; editing the Relationship changes the kind.
- Removing the `## Coordination` section, or the whole `CLAUDE.md`, removes all of that root's seed edges.
- The replacement is atomic — the root's prior seed edges are removed and the current ones inserted in
  one transaction, so a re-seed never leaves a partial set, and two concurrent seeds of the same root
  serialize rather than interleave.
- Operator-declared edges (`source=config`) are never touched — an operator edge always wins a collision
  on the same triple (see [project graph](understanding.md#project-graph)).
- Only the **canonical ref** is authoritative: a `## Coordination` change on a feature branch does not
  re-seed, because seeding rides the canonical-ref-gated push path.

This is what adopting the format buys: a repository that keeps its `## Coordination` table current gets
its product's edges tracked with no operator entry — a new sub-project appears as an edge on the next
canonical push, a retired one drops on the push that removes its row.

## Relationship to product membership

The member list is also the natural declaration of
[product membership](../concepts/product-scope.md#a-product-is-a-configured-set-of-repositories) — the
repositories that read as one product. Herald materializes the **edges** (the graph) from this table
today; consuming the same list as product membership is the forward-looking
[product-scope](../concepts/product-scope.md) direction. One file, one table, both relations.
