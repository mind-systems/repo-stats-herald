# 7.1.2 — Reasoner core (impl)

**Phase:** 7 — The reasoner over both memories. Depends on 7.1.1 (the `Reasoner` shape and its retrieval-invariant red tests). Second half of the reasoner-core milestone — turns 7.1.1's tests green and adds the real reasoning-prompt logic.

## Current state

7.1.1 defines `Reasoner.answer`'s signature and pins its retrieval-construction invariants (single embedding reused across both stores, correct `repo`-scoping, an honest no-memory path) with red tests over mocked collaborators. The stub raises for every call — no real embedding, no real store queries, no real prompt, no real generation exists yet.

## Change

Implement the real reasoning prompt and wire it to `LLMClient.generate`, using 7.1.1's retrieval mechanics unchanged.

- `src/reasoning/reasoner.py` — `Reasoner.answer`:
  1. embed `query` via the injected `Embedder` (3.2) — once, per 7.1.1's invariant (`embed([query])`, take `[0]`);
  2. `KnowledgeStore.query(embedding, k, repo=repo)` (semantic memory, Phase 3);
  3. `EpisodicStore.query(embedding, k, repo=repo)` (episodic memory, Phase 4 — `since`/`until` left at their `None` defaults: no time window, per the guard below);
  4. assemble a combined context — what the project is now (semantic results) and how it changed (episodic results, each carrying its `changed_at`);
  5. build a reasoning prompt instructing feature-level prose grounded in that context — including 7.1.1's honest no-memory framing when both stores are empty;
  6. `LLMClient.generate(prompt)` (Phase 1).

## Files & types

- edit `src/reasoning/reasoner.py` (stub → real `answer` implementation)
- extend `src/core/config.py` (`Settings.reasoner_k: int = 8`) and document it in `.env.example`; inject it into `Reasoner` at the composition root

## Guards

- `Reasoner` names no concrete model — it depends on `LLMClient` via constructor DI; swapping local↔hosted is a composition-root choice. Entitlement tiering (Phase 14) adds **zero** reasoner-side code.
- `k` is one retrieval size read from `Settings` at the composition root and injected (config-once — the reasoner reads no env directly), the **same** value for both store queries: `Settings.reasoner_k`, default `8`.
- `repo` is the bare `push.repo` key (never `org/repo`) — the same identity both stores are keyed by — passed through unchanged to both queries.
- **Retrieval + context assembly is a reusable internal helper** — steps 1–4 (embed once, both-store queries, combined context) live in an internal `_gather_context(query, repo)`-style method that `answer` calls before building its prompt; `answer` is only that helper plus the Q&A prompt and `generate`. 7.2 extends this same helper (neighbor folding) and 8.1's `narrate` reuses it — so cross-project reach and narration share one retrieval path, never a copy inlined in `answer`.
- Episodic retrieval is by similarity only for now — no explicit natural-language "6 months ago" → `since`/`until` parsing; the LLM reasons over the retrieved entries' `changed_at` values as context. Explicit time-window extraction is a later enhancement, not required here.
- Empty or failed retrieval from either store degrades to answering from whatever is available — never crashes, never silently empty.
- Turns 7.1.1's tests green — introduces no new retrieval-construction behavior beyond what 7.1.1 already pinned.

## Verification

- 7.1.1's red test suite passes green against this implementation.
- A query about a served project ("what does X do", "what's its direction") → prose grounded in its semantic memory (and episodic memory where relevant).
- A query about a past change ("when did X change", "what happened to Y") → surfaces the relevant episodic entries in the answer.
- A query against an unserved/unknown repo → an honest "no memory for this project" answer, not a fabricated one.
- Run through **the eval harness**, same discipline as summarization (Phase 1) and code distillation (5.2): a fixed `{repo, query}` case's answer is diffed against a **user-authored** reference answer (never fabricated) — verifying the reasoning prose itself stays grounded and reads well, beyond what the retrieval-invariant tests in 7.1.1 can check.
