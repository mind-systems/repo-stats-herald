## Plan Review Summary

**Plan:** `.ai-factory/plans/73-ollama-clients-transport-driven-suite.md`
**Roadmap line:** `ROADMAP_TESTS.md:23` — *"Ollama clients — transport-driven suite"*
**Governing spec:** `.ai-factory/specs/80-ollama-clients-test-plan.md`
**Risk Level:** 🟢 Low
**Review round:** 2 (re-review after round 1's two non-blocking clarifications)

### Context Gates
- **Architecture** (`.ai-factory/ARCHITECTURE.md` / project CLAUDE.md): PASS. Test-only plan touching `tests/llm/`, asserting against the `src/llm/` boundary. It honors the model-agnostic LLM seam (`LLMClient`/`Embedder` name no vendor concept) and drives every case through the injected `transport` seam with real `httpx.Response` objects — the injection/composition-root discipline the architecture mandates. No `src/` edits, no feature-to-feature coupling.
- **Rules** (`.ai-factory/RULES.md` present): PASS. The file is deliberately empty (no project counter-defaults); nothing in the planned artifacts violates it. The plan also respects the docs-style rule barring plan/spec/`.ai-factory` references inside code — Task 2 explicitly requires the deliberate-gap comment be "about behaviour only".
- **Roadmap linkage:** PASS. Resolves cleanly to `ROADMAP_TESTS.md:23` (spec `80-…`), not the unrelated `73`-prefixed EpisodicBackfill entries — the plan-file number is a plan sequence id, not the roadmap task number. The `DEVIATION` block is well-grounded and confirmed against source: `tests/llm/test_client.py` already fully covers `OllamaClient` (response parsing, transport, request composition, timeout plumbing) and `src/llm/client.py` already carries the generator guards — both landed by main-roadmap `23.5`, exactly as the roadmap line's Scope note and spec 80 predicted. Scoping this plan to the embedder suite + shared ABC guard is correct, not an omission.
- **Skill-context** (`.ai-factory/skill-context/aif-review/SKILL.md`): none present (`.ai-factory/skill-context/` is empty) — no project overrides to apply.

### Round-1 findings — both resolved
1. **ABC "no vendor concept" guard source scope** (round 1, finding 1) — RESOLVED. Task 4 now pins the mechanism explicitly: *"scoping the source read to the ABC **class body** via `inspect.getsource(LLMClient)` / `inspect.getsource(Embedder)` — NOT the whole module file"*, and spells out why a whole-file `"ollama" not in open(file).read()` form fails red for the wrong reason (both modules carry `"Ollama"` outside the ABC — the concrete class name plus error strings). The wrong-reason-red trap is closed.
2. **Carry spec 80's "deliberate gap" comment** (round 1, finding 2) — RESOLVED. Task 2's final bullet now mandates a short behaviour-only comment near the dimension-consistency cases recording that the check is scoped to a single `embed` call (nothing cross-call or against the model's expected dim; that half is enforced at the pgvector column on insert).

### Verification against ground truth
Re-checked every load-bearing claim against source this round, not carried over on faith:
- `OllamaEmbedder.__init__(base_url, model, api_key=None, timeout=120.0, transport=None)` — matches the fixture note's construction and the `120.0` default assertion (`embedder.py:11-24`). ✓
- Endpoint `/api/embed`, body `{"model", "input": texts}` — confirmed at `embedder.py:35-38` (batch API, `input` key — not `/api/embeddings`, not `prompt`/`texts`). ✓
- Validation order and shape — `if not embeddings` (catches missing-key `None` **and** empty list in one expression) → count check naming both counts → `any(not vector …)` empty-vector → `{len(v)}` dimension-set check (`embedder.py:43-55`). Task 2's cases and their placement (empty vector in a *non-first* position; dimension case asserting set membership, not string order) line up exactly. ✓
- Empty-input short-circuit `if not texts: return []` before any HTTP call (`embedder.py:27-28`) — the "no recorded call" assertion is valid. ✓
- Single-element hot path — confirmed live: `Reasoner` (`src/reasoning/reasoner.py:71`) does `(await self._embedder.embed([query]))[0]`; `writer.py:46` and `backfill.py:125,164` unpack `[embedding] = await …embed([content])`; `indexer.py:43` embeds the chunk batch. The added Task 1 single-element case is justified. ✓
- Header composition — `if self._api_key:` (`embedder.py:31`) is falsy on both `None` and `""`, so the Task 3 parametrization pinning both values is correct and defeats a "tighten to `is not None`" regression. ✓
- Transport failures — `response.raise_for_status()` (`embedder.py:40`) yields `httpx.HTTPStatusError` on 500; a handler that raises `httpx.ReadTimeout` propagates unswallowed (no `except` around the call). Both Task 3 cases are accurate. ✓
- Fixture note — `make_client` in `tests/llm/conftest.py` exposes `BASE_URL`/`MODEL` module constants and the recording-handler shape the `make_embedder` note mirrors exactly (same `(client, calls)` return contract, same transport-injection discipline). ✓
- Test-runner conventions — `pyproject.toml` sets `asyncio_mode = "auto"` with `pytest-asyncio` installed, so the plan's bare `async def` test cases (matching the existing `test_client.py` style) run without per-test decorators. ✓
- `tests/llm/__init__.py` and `conftest.py` already exist — the plan correctly neither re-creates them nor re-specifies the client suite.

Coverage remains complete relative to spec 80: all three batching behaviours (empty→no request, positional alignment, single request), all six response-validation guards plus the negative control, request composition + transport failure, and the two ABC-conformance assertions are present — plus the single-element-batch case spec 80 flags in its Gotchas.

### Critical Issues
None. The plan is implementable as written and will produce a correct, non-flaky suite.

### Positive Notes
- The `DEVIATION` block does real work: it reconciles the stale roadmap line ("both clients") against ground truth (the client suite already landed by 23.5) and confirms it *against source*, avoiding a duplicate `OllamaClient` suite — a clean application of "code wins over description."
- The fixture note names the exact failure mode of forgetting the transport (a real request reaches the SSH tunnel and hangs the full 120s before failing *like a legitimate error assertion*), and prescribes distinguishable one-dimensional vectors (`[1.0]`, `[2.0]`, `[3.0]`) so a reordering is *visible* — directly defeating the count-only-assertion blind spot.
- Subtle traps are pre-empted rather than left to the implementer: empty vector in a non-first position (defeats an `if not embeddings[0]` guard), set-membership assertion for the dimension message (unstable set repr), parametrizing missing-key with empty-list (so a future `is None` / `== []` split can't drop a branch), and `api_key=""` alongside `None`.
- Both round-1 clarifications were folded in precisely, and finding 1 in particular now removes the only path to a wrong-reason red test.

The plan is solid and ready to implement.

PLAN_REVIEW_PASS
