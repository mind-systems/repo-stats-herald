## Code Review Summary

**Files Reviewed:** 1 plan (`14-3-2-ollama-embeddings-boundary.md`), targeting `src/core/config.py`, `.env.example`, and new `src/llm/embedder.py`
**Risk Level:** 🟢 Low

Reviewed against the governing chain: roadmap line **3.2**, spec `.ai-factory/specs/05-ollama-embeddings-boundary.md`, and ground-truth code (`src/llm/client.py`, `src/core/config.py`, `.env.example`, `.ai-factory/ARCHITECTURE.md`). This is round 2; plan-review-1's single Critical (env-key mismatch) is re-checked below.

### Context Gates

- **Architecture** (`.ai-factory/ARCHITECTURE.md`): PASS. The plan honours every seam — a model-agnostic `Embedder` ABC that names no Ollama concept, a concrete `OllamaEmbedder`, a constructor taking primitives (`base_url`/`model`/`api_key`/`timeout`), and no env read inside the class. Deferring composition-root wiring to the first real consumer (3.4 indexer) matches the "introduce the abstraction when a real consumer is imminent, not speculatively" rule (ARCHITECTURE.md line 84); wiring now would be dead code. The ABC-with-one-impl shape mirrors the existing `LLMClient`/`OllamaClient` and is mandated by the spec's model-agnostic guard (the Phase 14 hosted-tier swap is the imminent second backend), so it is not speculative abstraction.
- **Rules** (`.ai-factory/RULES.md`): PASS. File is intentionally empty (documented as the correct result); nothing to enforce.
- **Roadmap** (`.ai-factory/ROADMAP.md`): Task 3.2 is the plan's target and sits at the active `[ ]` seam. The contract line names `/api/embeddings`; the spec explicitly permits "`/api/embeddings` (or `/api/embed` batch)", and the plan's choice of `/api/embed` is the spec-conformant reconciliation (see Positive Notes) — not an undocumented drift.
- **Skill-context** (`aif-review/SKILL.md`): absent — no project-specific review overrides.

### Critical Issues

None.

**Re-check of plan-review-1 Critical #1 (env-key mismatch): RESOLVED.**
Round 1 flagged that documenting the env key as `OLLAMA_EMBED_MODEL` while naming the field `embed_model` would be silently discarded under `extra="ignore"`. Task 1 now fixes the field name as `embed_model` and mandates the `.env.example` key text be exactly `EMBED_MODEL`, with an explicit note that an `OLLAMA_`-prefixed key would be silently ignored. This is correct: `Settings` declares no `env_prefix` and no aliases (confirmed in `config.py` line 9), so pydantic-settings binds `embed_model` to the uppercased field name `EMBED_MODEL`, exactly as `ollama_model` → `OLLAMA_MODEL`. The hazard is closed.

### Positive Notes

- **Endpoint and payload are correct.** `/api/embed` with `{"model", "input": texts}` → `embeddings` is Ollama's native batch endpoint (string-or-list `input`, aligned `embeddings` list out). It is the only shape that expresses the `list[str] -> list[list[float]]` batch contract; the legacy `/api/embeddings` takes a single `prompt` and returns one `embedding`. Spec-conformant.
- **Boundary discipline matches `OllamaClient` exactly.** Constructor `(base_url, model, api_key=None, timeout=120.0)`, bearer header added only when `api_key` is set, `raise_for_status()` so timeouts/transport/HTTP errors propagate — a faithful mirror of the generation client.
- **Failure guards satisfy the spec's "empty/malformed raises, never `[]`" invariant.** Missing/empty `embeddings`, length ≠ `len(texts)`, empty inner vector, and cross-vector dimension mismatch all raise `ValueError`; the `texts == []` short-circuit (return `[]` with no request) is a sensible edge case ordered before any indexing, so the dimension assertions cannot hit an empty list.

## Deferred observations

- Affects: task 3.3 (`vector(<dim>)` column) / task 3.4 (Artifact indexer) — Consistent with the plan's `Testing: no`, there is no automated verification here; the roadmap's "through the tunnel, `embed([...])` → fixed-dim vectors" stays a manual tunnel call. Before 3.3 pins the store's `vector(<dim>)` column, someone should exercise `OllamaEmbedder.embed` against the live `nomic-embed-text` model through the tunnel so the configured model's real dimension is known — the embedder guarantees a stable dimension but never asserts a specific one, by design.

PLAN_REVIEW_PASS
