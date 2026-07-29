## Code Review Summary

**Artifact reviewed:** `.ai-factory/plans/59-23-5-make-the-generator-refuse-an-empty-answer.md`
**Files targeted by the plan:** `src/llm/client.py`, `tests/llm/__init__.py`, `tests/llm/conftest.py`, `tests/llm/test_client.py`
**Risk Level:** 🟢 Low

### Context Gates

- **Roadmap (ROADMAP.md:128, task 23.5):** WARN — the contract line's `Spec:` tag names `.ai-factory/specs/85-llm-generate-response-guard.md` as the governing spec for this task, plus `80-ollama-clients-test-plan.md` for the cases. The plan's Context and tasks cite only spec 80; spec 85 is never linked. Content-wise the plan fully satisfies spec 85 (non-object body / absent key / empty-or-whitespace text each raise a `ValueError` naming the client and defect; real text returned unstripped; embedder and ABC untouched; whitespace-only-is-empty pinned deliberately). This is a doc-linkage gap, not a behavioral divergence — the plan implements the right thing, it just does not name its primary governing spec. Non-blocking.
- **Architecture (ARCHITECTURE.md):** PASS — the change stays inside `src/llm/`, edits only the concrete `OllamaClient`, adds no cross-feature imports, and leaves the `LLMClient` ABC free of any validation/transport concept. Consistent with the "wire concretes only at the composition root / LLM seam stays model-agnostic" rules in CLAUDE.md.
- **Rules (RULES.md):** PASS — file is intentionally empty (no counter-defaults); nothing to violate.

### Critical Issues

None. The plan is implementable as written and grounded in ground truth:

- **Task 1 is correct and correctly ordered.** `OllamaClient.generate` today ends in `return response.json()["response"]` (client.py:38) with zero validation, while `OllamaEmbedder.embed` (embedder.py:43–57) applies its four guards — the asymmetry the plan targets is real. The plan's check order (not-`dict` → missing key → empty/whitespace text → return unstripped) is the safe order: the `isinstance(body, dict)` guard precedes any `body["response"]` access, so a `None`/string body cannot fall through to a `TypeError`. The `"Ollama ..."` message convention matches the embedder's existing messages.
- **Test approach uses the right seam.** The plan correctly follows the superseding "Seam in place" section of spec 80 (`httpx.MockTransport` + real `httpx.Response`) rather than the deprecated `FakeAsyncClient`/monkeypatch pattern from that spec's earlier Instantiation section. The `transport` parameter is confirmed present on `OllamaClient.__init__` (client.py:18, threaded into `httpx.AsyncClient` at client.py:31), landed by task 23.4.
- **Timeout-plumbing assertion is accurate.** `src/main.py:102` wires `OllamaClient(settings.ollama_url, settings.ollama_model, settings.ollama_api_key)` positionally and never passes `timeout`, so Task 4's claim that an unconfigured client carries `120.0` matches the constructor default (client.py:17) and production reality. `_timeout` is a real attribute (client.py:23), so asserting it directly is valid.
- **Scope boundaries respected.** Package-marker `__init__.py` convention holds (every `tests/*` package has one). `tests/llm/` does not yet exist, so Task 2 correctly establishes it. Guards against editing `embedder.py` and the ABC are explicit and match the roadmap/spec guards. Test roadmap (ROADMAP_TESTS.md:23) explicitly reserves the generator response-parsing group for 23.5 — no overlap conflict.

### Positive Notes

- Task decomposition is clean: behavior change (Task 1) → package/fixture scaffolding (Task 2) → high-value response-parsing cases (Task 3) → loud-failure filler (Task 4), with dependencies stated. This matches the test-philosophy sort in spec 80 (silent-failure cases are the deliverable; transport/header/timeout cases are filler layered on shared fixtures).
- The plan preserves the deliberate decisions from the spec verbatim — whitespace-only counts as empty, the `api_key=""` falsiness is pinned by parametrize so no one "tightens" it into shipping a bare `Bearer ` header, `stream: False` is asserted on the wire.
- "Return text exactly as received — no `.strip()`" is called out explicitly, protecting the guard-that-must-not-mutate against an over-eager implementer.

## Deferred observations

- Affects: implementation of Task 2 (`tests/llm/conftest.py`) — The plan describes the construction helper as building "a `httpx.MockTransport(handler)` ... [that] returns a real `httpx.Response`" and returning "the client factory and the recorded-calls list," but does not spell out how each case varies the response body/status/error the handler produces (the cases need `{"response": ""}`, whitespace, a key-less dict, a non-object body, and raised `ReadTimeout`/`ConnectError`/non-2xx). An implementer will naturally parameterize the factory over a response spec, so this is under-specification rather than a defect. Separately, spec 80's Gotchas suggest asserting the transport was actually invoked so a forgotten transport can't silently hang for the full 120s timeout; with `MockTransport` this risk is largely neutralized (a passed transport never touches the network), so it is optional. Neither point blocks the plan. [dismissed]

PLAN_REVIEW_PASS
