# Code Review: 7.1.2 — Reasoner core (impl)

**Scope reviewed (code changes only):** `src/reasoning/reasoner.py`, `src/reasoning/prompt.py` (new), `src/core/config.py`, `.env.example`, `scripts/eval.py`, `evals/cases.yaml`. Planning artifacts (`.ai-factory/**`) excluded from correctness review.

## Verification performed
- `uv run pytest tests/reasoning/` → **7 passed** (7.1.1's red suite turns green unchanged, no test edits).
- `uv run pytest` (full) → **85 passed**, no regressions elsewhere.
- `import scripts.eval` + `import src.reasoning.{reasoner,prompt}` → clean, confirming **no `reasoner ↔ prompt` import cycle** (review-1 issue #1 resolved: `ReasoningPromptBuilder.build` takes `Chunk`/`EpisodicEntry` value objects from their owning modules; `GatheredContext` stays private to `reasoner.py`).
- Confirmed **no reference file fabricated** — `evals/reference/` holds only `.gitkeep`, matching the plan's "user-authored, never fabricated" constraint.

## Behavior confirmed against the 7.1.1 invariants
- **Embed-once / shared object:** `embedding = (await self._embedder.embed([query]))[0]` is bound once and the *same object* is passed to both store queries — satisfies the `is` identity assertion.
- **Bare-`repo` passthrough:** `repo` is forwarded unchanged (`repo=repo`) to both `KnowledgeStore.query` and `EpisodicStore.query`; `None` stays `None`. Episodic `since`/`until` left at defaults (no time window), per spec.
- **No-memory distinguishability (Resolution B):** `ReasoningPromptBuilder.build` emits `_NO_MEMORY_TEMPLATE` only when *both* lists are empty, materially different from the grounded prompt; `answer` always reaches `generate`. Both-empty and both-raise produce the identical no-memory prompt → identical `generate` call, satisfying `test_both_stores_failing_falls_back_to_no_memory_path`.
- **Per-store failure isolation:** each `query` is wrapped in its own `try/except Exception` inside `_gather_context`, degrading to `[]` with a `logger.warning(exc_info=True)`; the embedding call sits outside the guard, matching the spec's scoping of degradation to the two stores. (`asyncio.CancelledError` is a `BaseException` in 3.13, so cooperative cancellation is not swallowed — correct.)

## Composition-root / config
- `scripts/eval.py`: pool is created **only when a `reasoner` case is loaded** (`pool = None` sentinel; `if any(case.type == "reasoner" ...)`), closed in `finally` under an `if pool is not None` guard. `summary`/`distill` cases run with no Postgres dependency — the review-1 issue #2 operability concern is resolved. If `create_pool` raises, `pool` stays `None` and the `finally` is a no-op — clean.
- `Reasoner` constructor adds `reasoner_k: int = 8` and optional `prompt: ReasoningPromptBuilder | None = None`, both defaulted, so the frozen four-arg 7.1.1 fixture still constructs. The eval root injects `reasoner_k=settings.reasoner_k` and a `ReasoningPromptBuilder()`. Concretes (`OllamaClient`/`OllamaEmbedder`/`PgVectorStore`/`PgEpisodicStore`) are wired only at the root — DI discipline intact, no concrete model named in `Reasoner`.
- `Settings.reasoner_k: int = 8` added; `REASONER_K=8` documented in `.env.example`. pydantic-settings coerces the env string to `int` — fine.

## Notes (non-blocking, no action required)
- `_render_chunk` produces `- [] {content}` when a chunk has neither `repo` nor `path` (both `None`). Cosmetic only — the LLM still receives the content; no correctness impact. Populated chunks from `PgVectorStore` always carry `repo`/`path`, so this only surfaces for hand-constructed chunks.
- `str.format` is used with template-only field names; substituted values (`query`, `chunk.content`, `entry.content`) are inserted verbatim and are never re-parsed, so brace characters in stored content cannot break rendering or inject fields. Safe.
- `evals/cases.yaml` `herald-self-query` `query` scalar ends with `?` but does not *begin* with one, so it parses as a plain YAML string — correct.

No bugs, security issues, or correctness problems found.

REVIEW_PASS
