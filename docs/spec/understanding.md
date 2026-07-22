# Understanding

What Herald knows about each project it serves, and how projects connect. This is the substrate narration reasons over: a standing per-project model plus a graph of the ties between projects.

## Per-project knowledge model

Herald keeps a standing model of every project it serves, so it understands a change in the context of the whole project rather than re-reading the repository each time. The model is what lets Herald narrate at the level of features and direction: a push says what moved, the model says what it means.

### What the model holds

Per project, distilled from that project's own curated artifacts:

- **Features** — the units of work the project is built from, at the level its own specs describe them.
- **Direction** — where the project is heading: the goals its roadmap and design docs state.
- **State** — for each feature, what is built versus what remains (from roadmap `[x]/[ ]` and shipped work).
- **Contracts** — what the project owns and consumes (proto, auth, endpoints).

### Sources — curated, not raw code

The model is built from the artifacts humans already maintain:

| Source | Contributes |
|--------|-------------|
| `CLAUDE.md` | Purpose, integration points, contract ownership |
| `ARCHITECTURE.md` | Module boundaries and internal connections |
| `docs/` design specs | Feature behavior and direction, in present tense |
| `ROADMAP.md` | Features, phases, built-vs-remaining state |

Raw code and commits are the *change signal* — what moved; the artifacts are the *understanding*. Which files count as sources is a per-project **source strategy** (see [architecture.md](../architecture.md)); the set above is the default profile.

### A per-project retrieval store

Each served project has its own retrieval store (RAG): its curated artifacts, chunked and embedded, queried by semantic similarity. A push pulls the thread — the commits, or the roadmap tasks they touch — and retrieval surfaces the relevant slices of the project's knowledge, so Herald reasons from what is related to the change rather than from the whole corpus or a guess about what matters.

The store holds the curated, feature-level artifacts — whole units that keep their point — rather than raw code chopped into fragments that drop it. Herald embeds the change and queries the store; it does not re-read a repository, or the organization, to summarize a push.

### Bought, not built

The retrieval layer is standard infrastructure, not Herald's invention:

- **Vector store** — `pgvector`; Postgres is already in the stack, so no new service.
- **Embeddings** — an embedding model on the same Ollama that serves generation: same host, no external API.
- **Retrieval** — a thin chunk → embed → upsert → query layer over the two.

Herald's own part is the curated corpus, the freshness discipline below, and the narration built on top (see [narration.md](narration.md)).

### Freshness is tied to git

The store is slaved to the artifacts in git — Herald keeps a **local mirror** of each served repo (a full clone, pulled on each push, using the installation token as the git credential), so it indexes the repo's real current files and neither drifts from them nor grows without bound:

- On ingest (see [ingestion.md](ingestion.md)), Herald pulls the mirror and re-embeds only the artifact files the push changed.
- Chunks are keyed by `(repo, path)`, so a changed file's new chunks replace its old ones — superseded content is removed, not accumulated.
- The store indexes the current state of the artifacts, not their history — its size tracks how many docs a project has now, not how long it has existed.

Freshness rides the same push events as everything else; there is no separate re-indexing ritual.

### Depth follows what a project exposes

A project is onboarded by feeding the store whatever it has. Full curated docs yield a deep model and feature-level narration (see [narration.md](narration.md)); a project that exposes only commits yields a shallow one and commit-level notes; a project whose planning lives in an external system feeds that in. One mechanism, varying depth — not a premium reserved for artifact-rich repos.

## Project graph

Most relationships between projects are already written down — a coordination root that lists its members, a `CLAUDE.md` that names the proto a project owns and the consumers that regenerate from it. Because those live in the projects' own docs, they are in the knowledge store and surface through retrieval. Herald needs no separate structure to find them.

The project graph exists for the relationships that are **not** written down.

### What it holds

Two tightly-coupled projects can depend on each other while cross-referencing nothing in their artifacts. Retrieval has no text to surface, and Herald cannot invent the link. Those couplings live in a small **configured registry** — directed edges an operator declares: this project depends on that one, this contract is consumed there. An edge names the two projects and the nature of the tie (contract, auth, dependency), so [cross-project narration](narration.md#cross-project-narration) follows it the same way it follows a retrieved relationship.

### Seeding from coordination roots

A repository that declares itself a coordination layer and lists its sub-projects can seed the registry directly — the membership and the contracts it states become edges with no hand-entry. The registry is the union of these and the operator's own edges.

### Fallback

A project with no edges — none retrieved, none configured — is narrated on its own. The cross-project layer simply does not activate for it.

The graph relates projects that are already distinct. Grouping several repositories into one **product** that reads as a single thing — and the tenant that owns it — is a forward-looking scope layer above this one; see [product scope](../concepts/product-scope.md).
