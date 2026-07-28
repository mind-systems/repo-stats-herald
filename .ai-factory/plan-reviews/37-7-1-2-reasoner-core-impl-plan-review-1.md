## Plan Review Summary

**Plan:** 7.1.2 — Reasoner core (impl)
**Files Reviewed (plan targets):** `src/reasoning/reasoner.py`, `src/reasoning/prompt.py` (new), `src/core/config.py`, `.env.example`, `scripts/eval.py`, `evals/cases.yaml`
**Risk Level:** 🟢 Low

The plan is well-grounded: every "Key fact" was checked against ground truth and holds. Collaborator signatures (`Embedder.embed`, `KnowledgeStore.query`, `EpisodicStore.query`, `LLMClient.generate`), the four-arg constructor DI shape, the 7.1.1 fixture/tests, the `create_pool`/pool-lifecycle pattern in `scripts/backfill_episodic.py`, and the `PromptBuilder` convention all match what the plan describes. The Resolution-B no-memory design correctly satisfies every branch of the 7.1.1 suite, including `test_both_stores_failing_falls_back_to_no_memory_path` (both-empty and both-raise produce an identical `generate` call). The plan conforms to the governing spec `.ai-factory/specs/27-reasoner-core.md` and the ROADMAP contract line for 7.1.2.

### Context Gates
- **Architecture (`.ai-factory/ARCHITECTURE.md` / CLAUDE.md patterns):** PASS. `Reasoner` depends on `LLMClient`/`Embedder`/`KnowledgeStore`/`EpisodicStore` abstractions (public classes), wires concretes only at the `scripts/eval.py` composition root, reads config once at the root and injects `reasoner_k` — all consistent with the feature-modular DI rules. Prompt strings are localized to a dedicated `ReasoningPromptBuilder`, mirroring `src/summarization/prompt.py`.
- **Rules (`.ai-factory/RULES.md`):** PASS (file intentionally empty — no counter-defaults).
- **Roadmap:** PASS. Plan traces to ROADMAP line 78 (7.1.2) and its `Spec:` → `27-reasoner-core.md`; the guards (no concrete model named, single injected `Settings.reasoner_k` used for both stores, bare `push.repo` key, degrade-not-crash, reusable `_gather_context`) are all reflected in the tasks.
- **skill-context (`aif-review/SKILL.md`):** absent — no project overrides to apply.

### Critical Issues
None — no blocking defect.

### Issues

1. **Prompt-builder signature is under-pinned and its `build(query, gathered)` example invites a circular import (Task 2 / Task 3, `src/reasoning/prompt.py` ↔ `src/reasoning/reasoner.py`).**
   Task 3 defines `GatheredContext` *inside* `reasoner.py`, and `reasoner.py` imports `ReasoningPromptBuilder` from `prompt.py`. Task 2's parenthetical "`e.g. build(query, gathered)`" would make `prompt.py` import `GatheredContext` from `reasoner.py` — a `reasoner → prompt → reasoner` import cycle that fails at module load (the class is not yet bound when `prompt.py` is imported mid-initialization of `reasoner.py`). The established convention the plan says it mirrors avoids exactly this: `summarization/prompt.py`'s `PromptBuilder.build` takes `CommitContext` — a value object owned by *another* module (`commits.models`), never a type owned by `Summarizer`. Recommend pinning `ReasoningPromptBuilder.build` to take the domain value objects directly — `build(query, chunks: list[Chunk], entries: list[EpisodicEntry])` (imported from `knowledge`/`episodic`, matching the convention) — with `answer` unpacking `GatheredContext` into that call. If a single-argument shape is preferred for 7.2/8.1 reuse, `GatheredContext` must live in a neutral module both import (not in `reasoner.py`). Either way the plan should state the chosen signature so the implementer does not reach for the cycle-forming form.

2. **`scripts/eval.py` restructure makes `make eval` for the existing `summary`/`distill` cases newly depend on Postgres being up (Task 5).**
   Today `make eval` needs only the Ollama tunnel; the summarization/distillation cases never touch Postgres. Task 5 opens `pool = await create_pool(settings.postgres_dsn)` unconditionally at the top of `_run()`, so any `make eval` invocation — even one running only `herald-recent`/`tradeoxy-features` — now fails at pool creation if Postgres/pgvector isn't running. The plan's own note ("the reasoner is the only handler that needs the pool") argues for scoping the pool to when it's actually needed. Recommend opening the pool only when a `reasoner` case is present in the loaded cases (or lazily on first reasoner use), so the pre-existing cases keep running without a database. Low severity — the fix is small and within Task 5's file boundary — but it changes the operability contract of an existing command, so it belongs in the plan rather than left to the implementer to discover.

### Positive Notes
- The embedding-identity requirement (`embed([query])[0]` reused as the *same object* for both store calls) is called out explicitly in Task 3 — the exact invariant `test_answer_embeds_once_and_shares_embedding_with_both_stores` pins with `is`.
- Per-store failure isolation is correctly located inside `_gather_context` with embedding kept *outside* the degradation guard, matching the spec's scoping of degradation to the two stores.
- Backfill prerequisite in Task 6 is real and accurate: `scripts/backfill.py` populates the knowledge store and `scripts/backfill_episodic.py` the episodic log; the "never fabricate the reference" discipline mirrors the existing `tradeoxy-features` case comment.
- The `reasoner_k` default (`8`) and its optional `prompt` arg keep the frozen 7.1.1 four-arg fixture green while staying injectable at the root — correctly reasoned.

## Deferred observations
- Affects: task 7.2 (cross-project reach) — `GatheredContext` is introduced here as the shared retrieval shape that 7.2's neighbor folding and 8.1's `narrate` are meant to extend. If finding #1 is resolved by relocating it to a neutral module, that placement will also serve 7.2/8.1; if it stays in `reasoner.py`, 7.2 should re-evaluate whether the growing shape still belongs there. No action required within 7.1.2 beyond choosing a placement that does not force the import cycle.
