## Plan Review Summary

**Plan:** 7.1.2 — Reasoner core (impl)
**Files Reviewed (plan targets):** `src/reasoning/reasoner.py`, `src/reasoning/prompt.py` (new), `src/core/config.py`, `.env.example`, `scripts/eval.py`, `evals/cases.yaml`
**Risk Level:** 🟢 Low

This is the revised plan (round 2). Both issues raised in plan-review-1 are now resolved
in the plan text, and every ground-truth fact the plan rests on was re-verified against the
code and holds. The plan conforms to the governing spec `.ai-factory/specs/27-reasoner-core.md`,
the 7.1.1 contract spec `48-reasoner-contract.md`, and the frozen 7.1.1 test suite.

### Context Gates
- **Architecture (`.ai-factory/ARCHITECTURE.md` / CLAUDE.md patterns):** PASS. `Reasoner` depends
  only on the `LLMClient` / `Embedder` / `KnowledgeStore` / `EpisodicStore` abstractions (public
  classes), constructs no concrete client itself, and the concretes are wired solely at the
  `scripts/eval.py` composition root. `reasoner_k` is read once from `Settings` at the root and
  injected — the reasoner reads no env. Prompt strings are localized to a new
  `ReasoningPromptBuilder`, mirroring `src/summarization/prompt.py`. The `build(query, chunks, entries)`
  signature takes value objects owned by *other* feature modules (`Chunk` from `knowledge`,
  `EpisodicEntry` from `episodic`), exactly as `PromptBuilder.build(CommitContext)` does — no
  feature-to-feature internal coupling.
- **Rules (`.ai-factory/RULES.md`):** PASS (file empty — no counter-defaults).
- **Roadmap:** PASS. Plan traces to the 7.1.2 contract line and its `Spec:` → `27-reasoner-core.md`;
  every spec guard (no concrete model named, single injected `Settings.reasoner_k` feeding both
  stores, bare `push.repo` passthrough, degrade-not-crash, reusable `_gather_context`, episodic
  similarity-only with `since`/`until` left `None`) is reflected in the tasks.
- **skill-context (`aif-review/SKILL.md`):** absent — no project overrides to apply.

### Resolution of plan-review-1 findings
- **Finding #1 (import-cycle-prone prompt signature) — RESOLVED.** The Design-decisions section and
  Task 2 now pin `ReasoningPromptBuilder.build(query: str, chunks: list[Chunk], entries: list[EpisodicEntry]) -> str`,
  importing `Chunk` from `src/knowledge/store.py` and `EpisodicEntry` from `src/episodic/models.py`,
  and explicitly forbid taking `GatheredContext` (which stays internal to `reasoner.py`). Verified
  against ground truth: `Chunk` is defined in `src/knowledge/store.py` and `EpisodicEntry` in
  `src/episodic/models.py` — both import paths are correct, and neither module imports back from
  `reasoner.py`, so no `reasoner → prompt → reasoner` cycle is possible.
- **Finding #2 (`make eval` newly coupled to Postgres) — RESOLVED.** Task 5 now scopes the pool to
  reasoner cases: the pool is opened under `try/finally` *only when* a `type: reasoner` case is
  present in the loaded cases; the always-registered `summary`/`distill` handlers never touch it.
  The existing `make eval` (Ollama-tunnel-only) operability contract is preserved.

### Critical Issues
None — no blocking defect.

### Issues
None. Every concrete wiring claim in the plan was checked against the code and is accurate:
- `Reasoner(llm, embedder, knowledge, episodic)` matches the stub constructor and the frozen
  `tests/reasoning/conftest.py::reasoner` fixture (four keyword args). Adding `reasoner_k: int = 8`
  and `prompt: ReasoningPromptBuilder | None = None`, both defaulted, keeps that fixture green.
- Collaborator signatures match: `Embedder.embed(texts) -> list[list[float]]`,
  `KnowledgeStore.query(embedding, k, repo=None)`, `EpisodicStore.query(embedding, k, repo=None, since=None, until=None)`,
  `LLMClient.generate(prompt) -> str`.
- Composition-root concretes are correct: `OllamaClient(url, model, api_key)`,
  `OllamaEmbedder(url, embed_model, api_key)`, `PgVectorStore(pool)`, `PgEpisodicStore(pool)`,
  `create_pool(settings.postgres_dsn)` from `src/core/db.py` — all verified against
  `scripts/backfill_episodic.py` and the store/client sources. `settings.postgres_dsn` exists.
- The Resolution-B no-memory design satisfies every branch of the 7.1.1 suite. In particular,
  because `_gather_context` maps a raising store to `[]`, the both-empty and both-raise paths both
  produce `build(query, [], [])` → an identical `generate` call, satisfying
  `test_both_stores_failing_falls_back_to_no_memory_path`'s `both_raise_calls == no_memory_calls`;
  and the `if not chunks and not entries` no-memory branch yields text distinct from any grounded
  prompt, satisfying `test_honest_no_memory_is_distinguishable_from_grounded_path`.
- `ReasonerCaseHandler.run(inputs)` calling `await self._reasoner.answer(inputs["query"], inputs.get("repo"))`
  honors the `CaseHandler` contract (inputs→text, no filename logic) and passes the bare `repo` key
  or `None` unchanged, per the `_load_cases` inputs shape.
- Task 6's backfill prerequisite is real: `scripts/backfill.py` (knowledge) and
  `scripts/backfill_episodic.py` (episodic) both exist and populate the stores the reasoner queries.

### Positive Notes
- The embedding-identity invariant is called out with the exact `(await self._embedder.embed([query]))[0]`
  form and "reuse this same object", matching the `is` assertion in
  `test_answer_embeds_once_and_shares_embedding_with_both_stores`.
- Per-store failure isolation is correctly located inside `_gather_context`, with the single embed
  kept *outside* the degradation guard — matching the spec's scoping of degradation to the two stores
  (no 7.1.1 test exercises an embedder failure, so leaving it to propagate is correct).
- `GatheredContext` as a frozen internal result shape gives 7.2 (neighbor folding) and 8.1 (`narrate`)
  one retrieval path to extend, honoring the spec's reusable-helper guard.

## Deferred observations
- Affects: task 7.2 (cross-project reach) / 8.1 (narrate) — `GatheredContext` is introduced here as
  the shared retrieval shape those tasks are meant to extend, and this plan keeps it internal to
  `reasoner.py`. That placement is correct for 7.1.2 (it avoids the prompt-import cycle). If 7.2/8.1
  grow the shape or need `prompt.py` to consume it, they should re-evaluate relocating it to a neutral
  module both can import. No action required within 7.1.2.

PLAN_REVIEW_PASS
