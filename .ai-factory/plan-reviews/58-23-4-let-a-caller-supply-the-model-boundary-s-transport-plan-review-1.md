## Code Review Summary

**Files Reviewed:** 1 plan (targets `src/llm/client.py`, `src/llm/embedder.py`)
**Risk Level:** 🟢 Low

### Context Gates
- **Roadmap (`.ai-factory/ROADMAP.md:127`):** WARN-clear — the plan's `# Plan:` heading maps to the `23.4` contract line; scope (add optional `transport` on both concretes, keyword-with-default, boundary untouched, generator validation out) is a faithful subset of the line.
- **Governing spec (`.ai-factory/specs/84-llm-client-transport-seam.md`):** aligned. The two tasks realize the spec's `Change`, `Files & types`, and `Guards` clauses exactly — no drift, no additions.
- **Architecture (`.ai-factory/ARCHITECTURE.md` / CLAUDE.md):** compliant. The change lives entirely in the `src/llm/` boundary. Keeping the abstract `LLMClient`/`Embedder` free of any transport concept preserves the model-agnostic seam ("The LLM seam stays model-agnostic"). Keyword-with-default keeps the composition roots untouched, honoring "Config is read once at the root and injected."
- **Rules (`.ai-factory/RULES.md`):** empty by design; nothing to enforce.

### Critical Issues
None.

### Verification against ground truth
- **File paths:** correct. `src/llm/client.py` holds `OllamaClient`; `src/llm/embedder.py` holds `OllamaEmbedder`.
- **Constructor shape:** confirmed — both `__init__` end with `timeout: float = 120.0`, so appending `transport: httpx.AsyncBaseTransport | None = None` as the last parameter is accurate.
- **Client construction sites:** confirmed — `generate` builds `httpx.AsyncClient(timeout=self._timeout)` (client.py:29), `embed` builds the same (embedder.py:32). Both are the exact strings to amend.
- **API usage:** correct. `httpx.AsyncClient` accepts a `transport` keyword, and `httpx.AsyncBaseTransport` is the right abstract type (superclass of `httpx.MockTransport` and `ASGITransport`), so a `None` default cleanly falls back to httpx's own default transport.
- **`httpx` already imported** in both modules — no new import needed.
- **Boundary preservation:** the plan explicitly leaves the abstract `LLMClient`/`Embedder` and all embedder response-validation checks untouched, matching the spec's guard.
- **Scope discipline:** the plan correctly quarantines the generator's absent-response-validation asymmetry as a separate task, per the spec.

### Positive Notes
- Task 2 anchors to Task 1 ("Mirror Task 1 exactly") and enumerates the embedder's existing validation invariants to protect, leaving no room for the implementer to guess.
- No migration, security, or performance surface: additive keyword parameter, no DB/schema, no I/O change on the default path.
- `Testing: no` is consistent with the task's framing — this opens the seam; the coverage pass that exercises the supplied transport is Phase 23's separate work.

PLAN_REVIEW_PASS
