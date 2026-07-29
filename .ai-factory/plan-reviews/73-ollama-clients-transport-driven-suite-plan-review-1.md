## Plan Review Summary

**Plan:** `.ai-factory/plans/73-ollama-clients-transport-driven-suite.md`
**Roadmap line:** `ROADMAP_TESTS.md:23` — *"Ollama clients — transport-driven suite"*
**Governing spec:** `.ai-factory/specs/80-ollama-clients-test-plan.md`
**Risk Level:** 🟢 Low

### Context Gates
- **Architecture** (`.ai-factory/ARCHITECTURE.md` / project CLAUDE.md): PASS. The plan is a test-only plan touching `tests/llm/` and asserting against the `src/llm/` boundary. It respects the model-agnostic LLM seam (`LLMClient`/`Embedder` name no vendor concept) and drives everything through the injected `transport` seam — exactly the composition-root/injection discipline the architecture mandates. No `src/` edits, no feature-to-feature coupling.
- **Rules** (`.ai-factory/RULES.md` present): PASS. No convention violations spotted in the planned artifacts.
- **Roadmap linkage:** PASS. The plan resolves cleanly to `ROADMAP_TESTS.md:23` (spec `80-...`), not to the unrelated `73`-prefixed EpisodicBackfill entries — the plan-file number is a plan sequence id, not the roadmap task number. The `DEVIATION` annotation is well-grounded: `tests/llm/test_client.py` already exists and fully covers `OllamaClient` (response parsing, transport, request composition, timeout plumbing), and `src/llm/client.py` already carries the generator guards — both landed by main-roadmap `23.5`, exactly as spec 80's *"Still red: the generator's response-parsing group … land with it, not with the seam"* predicted. Scoping this plan to the embedder suite + shared ABC guard is correct, not an omission.
- **Skill-context** (`.ai-factory/skill-context/aif-review/SKILL.md`): none present — no project overrides to apply.

### Verification against ground truth
Every load-bearing claim in the plan was checked against source, not assumed:
- `OllamaEmbedder.__init__(base_url, model, api_key=None, timeout=120.0, transport=None)` — matches the fixture note's construction and the `120.0` default assertion. ✓
- Endpoint `/api/embed`, body `{"model", "input": texts}` — confirmed at `embedder.py:35-38` (batch API, `input` key, not `/api/embeddings`/`prompt`). ✓
- Validation order — `if not embeddings` (catches missing-key `None` **and** empty list in one expression) → count check → `any(not vector …)` empty-vector → `{len(v)}` dimension-set check. The plan's Task 2 cases and their placement (empty vector in a *non-first* position; dimension case asserting set membership rather than string order) line up exactly with the impl at `embedder.py:43-55`. ✓
- Empty-input short-circuit `if not texts: return []` before any HTTP call (`embedder.py:27-28`) — the "no recorded call" assertion is valid. ✓
- Single-element hot path — confirmed live: `Reasoner` (`src/reasoning/reasoner.py:71`) does `(await self._embedder.embed([query]))[0]`, and `writer.py`/`backfill.py` unpack `[embedding] = await …embed([content])`. The added Task 1 single-element case is justified. ✓
- `make_client` fixture in `tests/llm/conftest.py` exposes `BASE_URL`/`MODEL` module constants and the recording-handler shape the `make_embedder` fixture note mirrors. ✓
- `httpx` 0.28.1 in the env — `MockTransport`, `Response`, `ReadTimeout`, `HTTPStatusError` all available; the existing async `OllamaClient` tests already prove `MockTransport` works with `AsyncClient`. ✓
- `tests/llm/__init__.py` already exists — the plan correctly does not re-create it.

Coverage is complete relative to spec 80: all three batching behaviours, all six response-validation guards plus the negative control, request composition + transport, and the two ABC-conformance assertions are present, and the plan usefully adds the single-element-batch case that spec 80 flags in its Gotchas.

### Critical Issues
None. The plan is implementable as written and will produce a correct suite.

### Findings (non-blocking clarifications)

1. **Task 4, ABC "no vendor concept" guard — pin the source scope to the ABC class, not the module file.**
   The plan says *"read each ABC's module-level source (`src/llm/client.py`, `src/llm/embedder.py` at the ABC definitions) and assert the abstract interface names no vendor concept."* Ground truth: both module files contain `"Ollama"` **outside** the ABC — `src/llm/embedder.py` has 5 occurrences (`class OllamaEmbedder`, four `"Ollama embed response…"` error strings) and `src/llm/client.py` has 4. An implementer who reads the phrase literally — open the file, assert `"ollama" not in source` — ships a test that **fails red for the wrong reason**. The qualifier "at the ABC definitions" hints at the right scope, but the paired file paths pull the other way. Recommend pinning the mechanism explicitly, e.g. `inspect.getsource(Embedder)` / `inspect.getsource(LLMClient)` (which returns only the ABC class body — `async def embed(self, texts: list[str]) -> list[list[float]]: …`, no vendor token), so the guard is unambiguous and can't be mis-authored against the whole module. Loud/self-correcting, but a one-line pin removes the churn.

2. **Optional — carry spec 80's "deliberate gap" comment instruction into the test file.**
   Spec 80's Gotchas note that dimension stability is checked only *within* a single `embed` call (nothing cross-call or against the model's expected dim; the other half is enforced at the pgvector column), and it recommends *"a comment in the test file so the gap is deliberate."* The plan does not carry this instruction. It's advisory and non-blocking, but since the comment would live in the very file this task creates, it's cheap to fold in and keeps the known gap visible. (Keep the comment about behaviour only — no plan/spec/`.ai-factory` reference, per the docs-style rule.)

### Positive Notes
- The `DEVIATION` block does real work: it reconciles the stale plan-line ("both clients") against ground truth (client suite already landed by 23.5) and confirms it *against source*, avoiding a duplicate `OllamaClient` suite — a clean application of "code wins over description."
- The fixture note is excellent: it mandates the injected transport on every construction and names the exact failure mode of forgetting it (a real request reaches the SSH tunnel and hangs the full 120s before failing like a legitimate error assertion), and it prescribes distinguishable one-dimensional vectors (`[1.0]`, `[2.0]`, `[3.0]`) so a reordering is *visible* — directly defeating the count-only-assertion blind spot.
- Test-case selection follows the project's fail-silently philosophy: the response-validation and positional-ordering cases (silent corruption of retrieval ranking) are treated as high-value, while URL/500/header/timeout-plumbing cases are correctly framed as loud-failure filler that rides on fixtures already needed.
- Subtle traps are pre-empted rather than left to the implementer: empty vector in a non-first position (defeats an `if not embeddings[0]` guard), set-membership assertion for the dimension message (unstable set repr), parametrizing missing-key with empty-list (so a future `is None` / `== []` split can't drop a branch), and `api_key=""` alongside `None` (falsy-truthiness pin against a "tighten to `is not None`" regression that would ship `Bearer ` to the backend).

Two low, non-blocking clarifications are noted above; neither undermines the plan's correctness, but finding 1 is worth pinning before implementation to avoid a wrong-reason red test.
