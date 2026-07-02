## Plan Review: llm/ boundary (04-llm-boundary.md)

**Files Reviewed:** plan + spec note `04-llm-boundary.md`, `ARCHITECTURE.md`, `ROADMAP.md`, `rules/base.md`, `pyproject.toml`, `src/core/config.py`, `src/commits/` (convention reference)
**Risk Level:** 🟢 Low

The plan is a faithful, well-scoped decomposition of the ROADMAP `llm/ boundary` task and its spec note. Structure, dependency direction, and API shape all line up with the codebase as it actually exists.

### Context Gates

- **Architecture (`ARCHITECTURE.md`) — PASS.** The plan honors every relevant dependency rule:
  - `llm/` placed as an infra module (`src/llm/client.py`), matching the documented folder layout exactly.
  - `LLMClient` ABC exposes no Ollama concept (`generate(prompt) -> str`), satisfying "Abstractions at every external seam."
  - `OllamaClient.__init__` takes primitives (`base_url`, `model`, `api_key`, `timeout`) — never a `Settings` object — matching "Config is injected, not read ad hoc" and the anti-pattern against env reads inside modules.
  - Composition-root wiring (injecting `OllamaClient`) is correctly deferred to task 06, not smuggled in here.
- **Rules (`rules/base.md`) — WARN (stale file, not a plan defect).** `base.md` still describes a layer-first structure (`src/routes/`, `src/services/`, `src/models/`, `src/config.py`) that contradicts the feature-modular `ARCHITECTURE.md` and the real tree (`src/core/`, `src/commits/`). The plan correctly follows `ARCHITECTURE.md`. No action needed in this plan; flagging that `base.md` is auto-detected boilerplate and should eventually be reconciled so it stops contradicting the authoritative architecture doc. `base.md` also prescribes the `logging` module, but the plan's "Logging: minimal" + "errors raise, never silent" is consistent with the spec's guard — acceptable.
- **Roadmap (`ROADMAP.md`) — PASS.** Directly implements the `[ ] llm/ boundary` Phase-1 task; contract line and spec note (`notes/04-llm-boundary.md`) match the plan's tasks and guards one-to-one.

### Critical Issues

None. No missing migrations (no DB in scope), no security holes (bearer header added only when `api_key` set; no secrets in code — Settings already owns `ollama_api_key`), no wrong file paths (`src/llm/__init__.py`, `src/llm/client.py`, `pyproject.toml` all correct), no wrong API assumptions (Ollama `/api/generate` with `stream:false` returns a JSON object whose `response` field holds the text — correct).

### Minor Notes (non-blocking, implementer's discretion)

1. **`AsyncClient` lifecycle unspecified.** The plan says "using `httpx.AsyncClient` and the configured timeout" but not whether the client is created per `generate` call (`async with httpx.AsyncClient(timeout=...) as client:`) or held as an instance attribute. Per-call construction is the simplest correct choice for the spike and avoids leaking an unclosed client / event-loop binding issues. Worth stating so the implementer doesn't stash a long-lived client on `__init__` without a close path.
2. **URL join robustness.** `f"{base_url}/api/generate"` produces a double slash if `base_url` ever carries a trailing slash. The current default (`http://localhost:11434`) is clean, so this is cosmetic — an `rstrip("/")` on `base_url` would harden it cheaply.
3. **`response.json()["response"]` KeyError path.** If Ollama returns an unexpected shape, this raises `KeyError` rather than a silent empty string — which actually *satisfies* the spec guard ("errors surface as raised exceptions"). Called out only so it isn't mistaken for an oversight; no change required.
4. **Version pinning.** `httpx` is added unpinned, consistent with `fastapi`/`uvicorn` in the current `pyproject.toml`; fine as-is. The plan's instruction to run `uv lock`/`uv sync` is correct — `uv.lock` is present in the repo.

### Positive Notes

- Task dependency chain (dep → package init → implementation) is explicit and correct.
- The plan restates the load-bearing guards verbatim from the spec (no Ollama concept in the ABC, raise-don't-swallow, `stream:false`, no `Settings` in the client), so the implementer can't miss them.
- Correctly scopes out testing (Settings: Testing = no) and defers wiring to the composition-root task, avoiding scope creep.

PLAN_REVIEW_PASS
