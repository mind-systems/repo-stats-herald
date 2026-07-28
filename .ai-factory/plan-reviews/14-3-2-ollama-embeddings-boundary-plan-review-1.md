## Code Review Summary

**Files Reviewed:** 1 plan (`14-3-2-ollama-embeddings-boundary.md`), targeting `src/core/config.py`, `.env.example`, and new `src/llm/embedder.py`
**Risk Level:** 🟡 Medium

Reviewed against the governing chain: roadmap line **3.2**, spec `.ai-factory/specs/05-ollama-embeddings-boundary.md`, and ground-truth code (`src/llm/client.py`, `src/core/config.py`, `.env.example`, `ARCHITECTURE.md`).

### Context Gates

- **Architecture** (`.ai-factory/ARCHITECTURE.md`): PASS. Plan honours the seams — a model-agnostic `Embedder` ABC named of no Ollama concept, a concrete `OllamaEmbedder`, constructor taking primitives (`base_url`/`model`/`api_key`/`timeout`), no env read inside the class. Deferring composition-root wiring to the first consumer (3.4 indexer) matches the "introduce the abstraction when a real consumer is imminent, not speculatively" rule — there is no consumer today, so wiring now would be dead code. Correct scoping.
- **Rules** (`.ai-factory/RULES.md`): PASS. File is intentionally empty; nothing to enforce.
- **Roadmap** (`.ai-factory/ROADMAP.md`): Task 3.2 is the plan's target and is above the stop. One benign endpoint deviation from the contract line, reconciled below.
- **Skill-context** (`aif-review/SKILL.md`): absent — no project-specific review overrides.

### Critical Issues

**1. Env-var name mismatch — the documented `OLLAMA_EMBED_MODEL` key is silently ignored (`config.py` / `.env.example`, Task 1).**
`Settings` declares no `env_prefix` and no aliases, so pydantic-settings maps each field to the env var whose name is the **uppercased field name**: `ollama_url`→`OLLAMA_URL`, `ollama_model`→`OLLAMA_MODEL` (confirmed by `ARCHITECTURE.md` line 74 and `config.py`). A field named **`embed_model`** therefore reads from **`EMBED_MODEL`**, not `OLLAMA_EMBED_MODEL`. But Task 1 instructs adding the field as `embed_model` *and* documenting the env key as `OLLAMA_EMBED_MODEL` in `.env.example`. With `model_config = SettingsConfigDict(..., extra="ignore")`, setting `OLLAMA_EMBED_MODEL` in `.env` is **silently discarded** — the field stays at its default and no error is raised. An operator who sets `OLLAMA_EMBED_MODEL=some-other-model` gets `nomic-embed-text` anyway, and since the embedder's vector dimension is fixed per model (and must match the 3.3 store column), a silently-ignored override is a real, quiet hazard.
The governing spec and roadmap both fix the field name as `embed_model`, so the field name is not the thing to change. Fix the plan to document the env key as **`EMBED_MODEL=nomic-embed-text`** in `.env.example` (it is fine to still place it directly under the Ollama block for readability, but the key text must be `EMBED_MODEL`). Alternatively, if grouping under the `OLLAMA_` prefix is desired, the field must be renamed to `ollama_embed_model` in *both* the field and the `.env.example` key — but that contradicts the spec/roadmap name, so the `EMBED_MODEL` fix is preferred.

### Positive Notes

- **Endpoint choice is correct and spec-conformant.** The roadmap contract line names `/api/embeddings`, but the spec explicitly permits "`/api/embeddings` (or `/api/embed` batch)". The plan picks `/api/embed` with `{"model", "input": texts}` → `embeddings`, which is the right call: the legacy `/api/embeddings` endpoint takes a single `prompt` and returns a single `embedding`, so it cannot express the `list[str] -> list[list[float]]` batch contract. This is a correct deviation (conformance to the spec), not a defect. The request/response shape matches Ollama's batch API.
- **Boundary discipline is faithful to `OllamaClient`.** Constructor shape `(base_url, model, api_key=None, timeout=120.0)`, bearer header only when `api_key` is set, `raise_for_status()` so timeouts/transport/HTTP errors propagate — all mirror the existing generation client exactly.
- **Failure guards are thorough and match the spec's "empty/malformed raises, never `[]`" invariant:** missing/empty `embeddings`, length ≠ `len(texts)`, empty inner vector, and cross-vector dimension mismatch all raise `ValueError`. The `texts == []` short-circuit (return `[]` without a request) is a sensible edge case.

## Deferred observations

- Affects: task 3.4 (Artifact indexer) / spec verification — The plan carries no automated verification and, correctly, no composition-root wiring (the first consumer is the 3.4 indexer). The roadmap's verify — "through the tunnel, `embed([...])` → fixed-dim vectors" — is thus a manual tunnel call with no harness or script in this task (consistent with the plan's `Testing: no` / `Docs: no` settings). Worth ensuring 3.4, or a one-off tunnel check, actually exercises `OllamaEmbedder.embed` against a live model before the store's `vector(<dim>)` column is pinned in 3.3, so the configured model's real dimension is known. [dismissed]

Fix the env-key mismatch (Critical #1) and the plan is otherwise ready.
