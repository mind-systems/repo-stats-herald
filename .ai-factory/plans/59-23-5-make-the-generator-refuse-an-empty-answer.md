# Plan: 23.5 — Make the generator refuse an empty answer

## Context
Bring `OllamaClient.generate` level with its sibling embedder: a successful response whose body is not an object, lacks the `response` key, or carries empty/whitespace-only text must raise the same exception type with a message naming the client and the defect — and land the generator's response cases from the test plan, establishing `tests/llm/`.

## Settings
- Testing: yes
- Logging: minimal
- Docs: no

## Tasks

### Phase 1: Guard the generator's response

- [x] **Task 1: Refuse an empty or malformed generate response**
  Files: `src/llm/client.py`
  In `OllamaClient.generate`, after `response.raise_for_status()`, decode the body once (`body = response.json()`) and validate it before returning, mirroring the discipline `OllamaEmbedder.embed` already applies in `src/llm/embedder.py` (raise `ValueError` with a message that names the client and the specific defect):
  - If `body` is not a `dict` (e.g. `None` or a bare string from a proxy/broken tunnel answering 200 with a non-object) → raise `ValueError` naming the client and that the response was not an object.
  - If the `"response"` key is absent → raise `ValueError` naming the client and the missing key (replaces today's bare `KeyError`).
  - Read the text under `"response"`; if it is empty or whitespace-only (`not text.strip()`) → raise `ValueError` naming the client and that the response text was empty.
  - Otherwise return the text **exactly as received** — no `.strip()`, no rewriting; real text behaves exactly as today.
  Match the embedder's message convention (`"Ollama ..."` phrasing) so both halves of the boundary fail the same way and a caller can catch one `ValueError`.
  Guards: do not touch the transport, the timeout, the conditional bearer header, the request body, or the `LLMClient` ABC (it gains no validation concept). Do not edit `src/llm/embedder.py`.

### Phase 2: Establish `tests/llm/` with the generator's cases

- [x] **Task 2: Add the `tests/llm/` package and transport-driven construction helper** (depends on Task 1)
  Files: `tests/llm/__init__.py`, `tests/llm/conftest.py`
  Create the package marker (`__init__.py`, as every test package in this repo has one). In `conftest.py` add the shared construction helper that drives `OllamaClient` through the injected `transport` seam (present since 23.4): build a `httpx.MockTransport(handler)` where the handler records each `httpx.Request` into a calls list and returns a real `httpx.Response`, then construct `OllamaClient(base_url, model, api_key=..., transport=httpx.MockTransport(handler))`. Return both the client factory and the recorded-calls list to the cases. Follow the superseding "Seam in place" section of `.ai-factory/specs/80-ollama-clients-test-plan.md` — use `httpx.MockTransport` with real `httpx.Response` objects; do **not** hand-write a `FakeAsyncClient`/`FakeResponse` stand-in or monkeypatch the module's `httpx.AsyncClient` symbol. Assertions read off the recorded request via `request.url`, `request.headers`, and `json.loads(request.content)`. `pyproject.toml` sets `asyncio_mode = "auto"`, so tests are plain `async def`.

- [x] **Task 3: Land the generator's response-parsing cases (the red-against-Task-0 core)** (depends on Task 2)
  Files: `tests/llm/test_client.py`
  Implement the four response-parsing cases from the test plan's "`OllamaClient.generate` — response parsing" group, each asserting a `ValueError` whose message identifies the client and the defect:
  - 200 body `{"response": ""}` → raises rather than returning `""`.
  - 200 body `{"response": "   \n  "}` (whitespace-only) → raises; pins the deliberate decision that whitespace-only counts as empty.
  - 200 body lacking the key, e.g. `{"model": "qwen2.5", "done": True}` → raises a typed `ValueError` naming the missing key (not a bare `KeyError`).
  - 200 body that is not a JSON object (`None` or a bare string) → raises.
  Add the positive control: a 200 body with real text returns exactly that text, unstripped (e.g. text with surrounding real content is returned byte-for-byte).

- [x] **Task 4: Land the generator's transport and request-composition cases** (depends on Task 2)
  Files: `tests/llm/test_client.py`
  Add the lower-value loud-failure and wire-contract cases from the test plan's "`OllamaClient.generate` — transport" and "request composition" groups, on top of the fixtures Task 2 already provides:
  - Transport: a handler raising `httpx.ReadTimeout` propagates; a non-2xx real response propagates via `raise_for_status`; `httpx.ConnectError` propagates. None are swallowed into a default.
  - Request composition: an `Authorization: Bearer <key>` header is attached when an api key is set; the header is omitted entirely when the key is `None` **and** when it is `""` (parametrize both — pins the incidental falsiness so no one "tightens" it into shipping `Bearer `). The request POSTs to `{base_url}/api/generate` with the configured model, the prompt, and `stream: False`.
  - Timeout plumbing: `MockTransport` bypasses the timeout, so assert `client._timeout` directly — both a configured value and that an unconfigured client carries `120.0` (production never passes `timeout`).
  Do not add embedder cases here — the embedder is untouched by this task and its coverage is a separate test-roadmap entry.
