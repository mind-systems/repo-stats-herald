# 7.1.1 — Reasoner contract + retrieval invariants (red tests)

**Phase:** 7 — The reasoner over both memories. Depends on Phase 3 (semantic memory + the embedder), Phase 4 (episodic memory), Phase 1 (`LLMClient`). First half of the reasoner-core milestone — the shape + retrieval invariants, pinned with red tests, ahead of the real reasoning-prompt implementation (7.1.2).

## Current state

Nothing answers an arbitrary question about a project. The existing narrator — now the reasoner's narrate (8.1) — only narrates one specific resolved push, reading `KnowledgeStore` (semantic memory) alone — it never touches `EpisodicStore` (episodic memory, Phase 4) and has no notion of a free-text query. `docs/architecture.md` names this general capability the **reasoner**: it turns a query and retrieved context from both memories into prose; narration is one mode of it, not the whole of it.

`Reasoner.answer` is the most heavily-reused surface downstream — 7.2 extends it directly, and 8.1 (narrate), 10.1 (report), 15.1 (`/ask`), and 15.2 (multi-turn sessions) all call or build on it — so its retrieval construction needs to be right before anything is built against it. Four invariants are currently asserted only in prose, each a real silent-failure surface:

- **one embedding, two stores** — a bug that re-embeds the query per store, or embeds it differently for each, wastes work and can silently desynchronize what "the same query" means across semantic and episodic results;
- **`repo`-scoping** — a bug that silently ignores the `repo` argument and always queries org-wide would silently break project isolation, no exception, just cross-contaminated answers;
- **honest no-memory** — when both stores return nothing, a naive implementation might still build a confident-sounding prompt as if grounded, inviting the LLM to invent an answer rather than say so;
- **failure isolation** — a store whose `query` **raises** must not crash `answer`: it degrades to whatever the other store returned (or the no-memory path if neither did), the exception never propagating. Pinned nowhere today, yet 7.1.2's degrade-don't-crash guard rests on it.

## Change

Define `Reasoner`'s shape and pin the three retrieval-construction invariants with red tests over mocked collaborators — no real LLM call, no real store. LLM-output *prose quality* is explicitly out of scope here; that's the eval harness's job, unchanged, and lands in 7.1.2.

- `src/reasoning/reasoner.py`:
  - `Reasoner` (a concrete class — the swap seam is the injected `LLMClient`, not the reasoner itself), constructed with `LLMClient`, `Embedder`, `KnowledgeStore`, `EpisodicStore` injected.
  - `answer(query: str, repo: str | None = None) -> str` — a STUBBED method (raises `NotImplementedError` for now) whose intended shape is: embed `query` once (`Embedder.embed(texts: list[str]) -> list[list[float]]` is a **batch** API, `src/llm/embedder.py` — call `embed([query])` and take `[0]`) → query `KnowledgeStore.query(embedding, k, repo=…)` (`src/knowledge/store.py`) and `EpisodicStore.query(embedding, k, repo=…)` (`src/episodic/store.py` — its `since`/`until` params default `None` and are **not** passed here: no time window) with that one embedding, scoped to `repo` when given else org-wide → assemble a combined context → build a reasoning prompt → `LLMClient.generate(prompt: str) -> str`. **`repo` is the bare `push.repo` name (never `org/repo`)** — the one key both stores are keyed by.
- Write red tests over mocked `Embedder`/`KnowledgeStore`/`EpisodicStore`/`LLMClient` pinning:
  - **one embedding, two stores** — `Embedder.embed` is called exactly once per `answer()` call; both `KnowledgeStore.query` and `EpisodicStore.query` are called with that same embedding vector;
  - **`repo`-scoping** — calling `answer(query, repo="api")` (a **bare** `push.repo` name, never `org/repo`) passes `repo="api"` to both stores' `query`; calling `answer(query)` (no `repo`) passes `repo=None` to both — never silently defaulting to org-wide when a repo was given, or vice versa;
  - **honest no-memory** — when both mocked stores return an empty result list, the prompt passed to `LLMClient.generate` carries an explicit no-memory marker/framing (or `answer` short-circuits before calling `generate` at all) — distinguishably different from the prompt built when either store returns results;
  - **failure isolation** — when one mocked store's `query` **raises** and the other returns results, `answer` still returns a string built from the surviving store's results (the raise is caught per-store, never propagated); when both raise, the no-memory path is taken — matching 7.1.2's degrade-don't-crash guard.

## Files & types

- new `src/reasoning/__init__.py`, `src/reasoning/reasoner.py` (`Reasoner`, stub `answer`)
- new test file(s) covering the three invariants above, run against mocked collaborators (red)

## Guards

- Tests-first: the stub raises — 7.1.2 turns these tests green, never redesigns them.
- All three tests run against **mocks only** — no real `LLMClient`, no real Postgres/pgvector. Whether the LLM's actual prose stays grounded and well-written is eval-harness territory (7.1.2), not asserted here.
- `Reasoner` names no concrete model — depends on `LLMClient` via constructor DI.
- One query embedding retrieves from **both** stores — this only works because the embedder is fixed per store (Phase 3's/Phase 4's shared invariant); a store-specific embedder would fork retrieval, which is exactly what the "called once" test guards against.

## Verification

- The test suite added here is red against the stub (fails only because `answer` has no logic yet).
- Each of the four pinned invariants (single embedding reused across both stores, correct `repo`-scoping passed through, structurally distinct no-memory prompt path, per-store failure isolation) has a corresponding red test.
