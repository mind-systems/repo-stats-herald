# Product Scope & Ownership (concept)

A forward-looking design. Today Herald treats one **repository** as one project: the two
memories — semantic and episodic — are keyed by repo, and the coarsest scope above a repo
is the **organization** (the GitHub App installation, the serve-allowlist unit; see
[ingestion.md](../behavior/ingestion.md)). This concept introduces the layer that sits between
them — a **product**, a configured group of repositories that reads as one thing — and the
**ownership root** above the organization that a multi-tenant Herald needs. It is written as
the target contract; it is not built, and nothing here commits to building it before a second
product in one organization must be served.

## Why

An organization is not a product. Under one GitHub organization `mind-systems` live two
unrelated products — a health platform across seven repositories (`mind_api`, `mind_mcp`,
`mind_mobile`, `mind_web`, …) and an unrelated platform in another domain, spanning its own
repositories. The current model has no name for that middle grouping, so it defaults
to the organization — and [org-wide retrieval](../behavior/narration.md#cross-project-narration)
would blend a change from that other platform into a health project's context, drawing ripple where none exists.

The grouping cannot be reliably inferred. A repository that declares itself a coordination
layer and lists its members can seed it (see [project-graph seeding](../behavior/understanding.md#seeding-from-coordination-roots)),
but many products have no such hub in git — their umbrella is a developer's local folder, not a
pushed repository. So membership is **declared**, not guessed.

## The scope hierarchy

| Level | What it is | Role |
|-------|-----------|------|
| **Tenant** | the account that owns the work and pays for it | the ownership root; links one or more GitHub organizations |
| **Product** | a configured set of repositories that reads as one thing | the retrieval, narration, and delivery scope — replaces "org-wide" |
| **Repository** | one git repo, with its two memories | the unit of the mirror and the stores; unchanged |

The GitHub **organization / installation** is an external identity axis, mapped onto a tenant —
not equal to a product. Today Herald collapses two of these joins: tenant with organization, and
product with repository. `mind-systems` breaks the second (one organization, many products); an
agency serving several clients' organizations breaks the first (one tenant, many organizations).

## A product is a configured set of repositories

Membership is routing state, read through the [resolver seam](../behavior/configuration.md#the-resolver-seam)
like every other, never inferred inline:

- **Declared** — an operator assigns repositories to a product in the configuration registry.
- **Seeded** — a coordination-root repository declares its members and their contracts in its
  `CLAUDE.md`, in the [coordination-root format](../behavior/coordination-root-format.md); Herald
  reads that from the canonical ref with no hand-entry. The same declaration feeds both relations —
  its member list is this membership, its stated contracts are the
  [project graph](../behavior/understanding.md#project-graph)'s dependency edges (materialized today;
  membership is this concept's forward-looking use).

A product is the scope a query and a narration run over: retrieval spans the product's
repositories, and cross-repository framing is *within-product* by default. A repository belongs
to exactly one product; a repository not yet assigned to any product is *dormant* — reachable but
not narrated — until it is composed into one (see [activation](#activation-nothing-runs-until-a-product-is-composed)).

## A product carries its own delivery channel

Delivery is scoped to the product, not the organization. Each product names its own Telegram
channel, so two products under one organization narrate to two channels instead of merging into
one. The resolver today keys the channel by organization (see
[configuration.md](../behavior/configuration.md#what-the-resolver-holds)); the product scope moves that
key onto the product, and a product with no channel set is simply not delivered.

## Activation: nothing runs until a product is composed

Being installed and served is necessary but not sufficient. A repository Herald can reach sits
**dormant** — mirrored and reachable, but not indexed or narrated — until it is composed into a
product. Composition is the activation signal, and the onboarding sequence is ordered by it:

1. **Authenticate** — the owner signs in with GitHub (OAuth); GitHub is the identity provider.
2. **Install** — the Herald App is installed on the chosen repositories, making them reachable.
3. **Compose** — available repositories are grouped into products, each given its channel and
   its languages.
4. **Then, and only then** — Herald indexes, narrates, and delivers for those products.

This inverts the default from "serve every repository in a served organization" to "serve only
repositories composed into a product," and it generalizes the operator
[serve-allowlist](../behavior/ingestion.md#who-herald-serves) into tenant self-service: a tenant
activates its own work by composing products, not an operator adding an organization id by hand.

## Membership and dependency are two relations

Product membership is not the [project graph](../behavior/understanding.md#project-graph)'s
dependency edge, and conflating them loses information:

- **Membership** binds repositories into one product — `mind_api` and `mind_mobile` are one
  product though neither "depends on" the other for ripple.
- **Dependency** is a directed edge between products — a contract one product owns and another
  consumes — and it is what [cross-project narration](../behavior/narration.md#cross-project-narration)
  follows to frame a change's effect elsewhere. Two separate products can
  share such an edge without being one product.

Within-product coherence runs on membership; cross-product ripple runs on dependency. The graph's
edges are between products, the coarser unit that makes ripple meaningful.

## Ownership: the tenant root

A tenant owns products and links the GitHub organizations its installations cover. This is the
entity a multi-tenant Herald bills, authorizes, and scopes access by — the root the current model
lacks entirely. A **user** — an individual human login — is a member of a tenant, and enters only
with the interface that lets a tenant self-manage; until then the tenant is the account and its
configuration is operator config. This is the layer the
[multi-tenant evolution](../behavior/configuration.md#evolution-of-the-backing-store) introduces.

## Where it lives and when to build

- Product membership and tenant ownership are **resolver-backed configuration**, riding the same
  environment → database → GUI ladder as the rest of the
  [routing state](../behavior/configuration.md#evolution-of-the-backing-store). Retrieval and narration
  read the product scope through the resolver; they never compute it.
- The **minimal build** — a configured `repositories → product` grouping and product-scoped
  retrieval — earns its place as soon as one organization serves a second product, which
  `mind-systems` already does. Full tenant, user, and entitlement modeling lands with the
  multi-tenant GUI stage.
- The **stores stay per-repository.** A product is a scope and a view, not a merged index —
  merging would break the per-repo freshness and supersession discipline
  ([freshness is tied to git](../behavior/understanding.md#freshness-is-tied-to-git)). "One product" is
  a lens over the repositories' stores, not one store.
- **Out of scope here:** how a single feature spans repositories when its truth lives outside code
  (a no-code task hub, mega-commits that bundle many features) is a separate concern of feature
  identity, not of product scope.
