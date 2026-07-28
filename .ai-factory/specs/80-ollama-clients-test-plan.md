# Ollama LLM & Embedder Clients — Test Plan

**Date:** 2026-07-29
**Source:** roadmap-test-coverage agent

> Two corrections to the research premise, both load-bearing:
>
> 1. **`.ai-factory/specs/04-llm-boundary.md` does not exist.** `04` is `04-repo-mirror.md`; the Phase-1 LLM boundary spec was pruned from `specs/`. Its guards survive only as quoted constraints inside `.ai-factory/specs/15-telegram-client.md`, which pins `OllamaClient`'s transport discipline as the reference pattern: bounded timeout + `raise_for_status()`, "never a silent no-op". `05-ollama-embeddings-boundary.md` does exist and is intact.
> 2. **The two files are asymmetric — `OllamaClient` has no response guard at all.** `src/llm/client.py` ends in `return response.json()["response"]`. The embedder has four guards; the generator has zero. So the highest-value cases in this plan are **red against current code**, not regression pins.

## Source Overview

`src/llm/client.py` holds `LLMClient` (ABC, one method `generate(prompt) -> str`) and `OllamaClient`, which POSTs `{model, prompt, stream: False}` to `{base_url}/api/generate` and returns `response.json()["response"]`. `src/llm/embedder.py` holds `Embedder` (ABC, `embed(texts) -> list[list[float]]`) and `OllamaEmbedder`, which POSTs `{model, input: texts}` to `{base_url}/api/embed` and validates the returned `embeddings` array against four guards before returning it.

The two are structurally twins — same constructor `(base_url, model, api_key=None, timeout=120.0)`, same conditional bearer header, same `httpx.AsyncClient(timeout=...)` context manager, same `raise_for_status()` — but they diverge exactly where it matters. **`OllamaEmbedder` validates its response body; `OllamaClient` does not.** A 200 whose body is `{"response": ""}` returns an empty string to the caller with no error, and a 200 missing the key raises a bare `KeyError`. That asymmetry is what this plan targets.

## Instantiation

**Reuse the `FakeAsyncClient` / `FakeResponse` monkeypatch pattern.** It is the project's established way to fake `httpx` and lives in two near-identical copies:

- `tests/delivery/test_telegram_client.py` — the minimal form (`FakeResponse` with only `raise_for_status`).
- `tests/delivery/test_changelog_client.py` — the form to copy here, because its `FakeResponse` also carries a configurable `json()` body.

The project does **not** use `httpx.MockTransport` and does not stand up a local server anywhere. Do not introduce either; match what exists.

The shape:

- `FakeResponse(body, error)` — `raise_for_status()` no-ops unless `error` is set, then raises it; `json()` returns `body`.
- `FakeAsyncClient` — an async context manager whose `post(url, json, headers)` records the call and returns a `FakeResponse`.
- `_install_fake_transport(monkeypatch, ...)` — a factory monkeypatched over the module's `httpx.AsyncClient` symbol, returning the recorded-calls list.

Two adaptations are required, both non-obvious:

1. **Patch the right symbol.** `monkeypatch.setattr("src.llm.client.httpx.AsyncClient", factory)` and `monkeypatch.setattr("src.llm.embedder.httpx.AsyncClient", factory)`.
2. **Record `headers` and the constructor kwargs.** Both delivery fakes take `post(url, json)` only — neither client under test passes headers. Here, `post` must accept `headers=...` and record it, and the `factory(*args, **kwargs)` must record `kwargs["timeout"]`.

Put the shared fakes in a new `tests/llm/conftest.py` (with `tests/llm/__init__.py` — every test package in this repo has one). `pyproject.toml` sets `asyncio_mode = "auto"`.

Reference constructor values, from the composition root in `src/main.py` — both wire positionally as `(settings.ollama_url, settings.<model>, settings.ollama_api_key)` and **never pass `timeout`**, so the `120.0` default is what production actually runs on.

Note also `tests/reasoning/conftest.py`, which already defines `FakeEmbedder(Embedder)` and `FakeLLMClient(LLMClient)`. Those are ABC-conformance fakes for *consumers* of the boundary and exercise no transport.

## Existing Coverage

**None.** There is no `tests/llm/` directory. `src/llm/client.py` and `src/llm/embedder.py` have zero direct tests. The only test-suite contact is indirect, through the ABCs (`tests/reasoning/conftest.py`, `tests/knowledge/test_code_distiller_contract.py`), never the Ollama implementations. The response-parsing guards on `OllamaEmbedder` were written without tests; the equivalent guards on `OllamaClient` were never written at all.

## Test Cases

### `OllamaClient.generate` — response parsing (HIGH VALUE)

These four are the reason this plan exists. All are **red against current code**. An empty summary here flows through `Reasoner.narrate` → the localizer → `TelegramClient.send` and lands in the channel as a blank note, with no exception anywhere in the chain.

- **should raise rather than return an empty string when the 200 body is `{"response": ""}`** — the single highest-value test in the plan: the one failure mode that is both silent and end-user-visible. Currently returns `""`.
- **should raise rather than return an empty string when the 200 body's `response` is whitespace-only** — body `{"response": "   \n  "}`. Non-obvious: a `if not text` guard passes this through; the guard must strip. Whether this counts as empty is a genuine decision the implementation has to make — pin it deliberately.
- **should raise a meaningful error when the 200 body lacks the `response` key** — body `{"model": "qwen2.5", "done": True}` — a plausible Ollama shape when a request is malformed or the model is missing. Currently raises `KeyError('response')`; assert on a typed error (mirror the embedder's `ValueError` with a message naming the client and the missing key).
- **should raise when the 200 body is not a JSON object at all** — body `None` or `"some string"`. Guards against a proxy or tunnel returning 200 with a non-JSON payload.

### `OllamaClient.generate` — transport (LOWER VALUE, loud-failure filler)

- **should propagate the error rather than return a default when the request times out** — set `error=httpx.ReadTimeout` on the fake. Non-obvious: the fake's `error` is raised from `raise_for_status()`, so this simulates the *effect* of a timeout, not a real one. For fidelity, have `FakeAsyncClient.post` raise when the error is a `TimeoutException` subclass and have `raise_for_status` raise otherwise — the spec's "timeouts raise, never a silently empty summary" is about the transport call, not the status check.
- **should propagate the error when the backend returns a non-2xx** — `error=httpx.HTTPStatusError(..., request=None, response=None)`; the existing tests pass those as `None` and `httpx` tolerates it.
- **should propagate the error when the connection fails outright** — `error=httpx.ConnectError`. The realistic dev failure: the SSH tunnel (`make tunnel`) is down.

### `OllamaClient.generate` — request composition (LOWER VALUE)

- **should attach an `Authorization: Bearer <key>` header when an api key is set.**
- **should omit the `Authorization` header entirely when no api key is set** — also cover `api_key=""` in the same parametrize. The guard is `if self._api_key:`, so empty string is falsy and correctly omits — but that is incidental truthiness, not an explicit `is not None`, and pinning it prevents someone "tightening" it and shipping `Bearer ` to the backend. `Settings.ollama_api_key` reads from env, where an unset var can easily arrive as `""`.
- **should POST to `{base_url}/api/generate` with the configured model, the prompt, and `stream: False`** — `stream: False` matters: with streaming on, the body is NDJSON and `.json()` would parse only the first frame.
- **should pass the configured timeout to the underlying client** — and separately that an unconfigured client receives `120.0`. Production never passes `timeout`, so the default is the real value.

### `OllamaEmbedder.embed` — batching and the empty-input short-circuit

- **should return an empty list without issuing any HTTP request when given an empty text list** — assert `result == []` **and** that the recorded-calls list is empty. Non-obvious and the reason this is not filler: the source returns `[]` before touching the network. That is the one legitimate empty return in either file, and it is easy for a later refactor to move the guard below the request (harmless) or delete it (a POST with `input: []`, which Ollama answers with an error). Assert on the *absence of the call*.
- **should return one vector per input text, in order, for a well-formed batch** — ordering is an unstated but load-bearing contract: callers in `src/knowledge/` zip these vectors back against their source chunks by index, so a reordering silently mislabels every embedding.
- **should send all texts in a single request rather than one request per text** — spec 05 says "batches the input texts"; a per-text loop would still pass every other test here while multiplying tunnel round-trips.

### `OllamaEmbedder.embed` — response validation (HIGH VALUE)

These pin the four existing guards. They are green today; they are high-value as **regression pins**, because each guard is a two-line check with no test holding it in place, and a wrong or missing vector poisons retrieval ranking without any crash.

- **should raise rather than return an empty list when the 200 body lacks the `embeddings` key** — covers `body.get("embeddings")` returning `None`. Non-obvious: this also guards a real API-shape hazard — Ollama's older `/api/embeddings` endpoint returns singular `{"embedding": [...]}`, and a URL change would land here.
- **should raise rather than return an empty list when `embeddings` is an empty list** — the `if not embeddings` guard catches missing-key and empty-list in one expression; parametrize both so a future split into `is None` / `== []` cannot drop one branch.
- **should raise when the response returns fewer vectors than texts** — **the highest-value case in this class:** silent and corrupting rather than merely absent. Without the guard, a caller zipping vectors to chunks by index would associate every chunk after the gap with the wrong embedding, and retrieval would return confidently wrong neighbours forever. Assert the message names both counts.
- **should raise when the response returns more vectors than texts** — same `len(...) != len(...)` guard, other side.
- **should raise when any returned vector is empty** — body `{"embeddings": [[0.1, 0.2], []]}`. Non-obvious: an empty vector passes the length check (the *count* is right) and would reach pgvector as a zero-dimension value. Put the empty vector in a non-first position — a guard written as `if not embeddings[0]` would pass a first-position-only test.
- **should raise when vectors have inconsistent dimensions across a batch** — assert the error message names the conflicting dimensions (the implementation formats a set, so assert on membership of both numbers rather than exact string order — set repr ordering is not stable).
- **should accept a batch where all vectors share one dimension** — the negative control. Without it, a guard mistakenly written as `if len(dimensions) >= 1` would pass every failure test above and reject all valid input.

### `OllamaEmbedder.embed` — transport and request composition (LOWER VALUE)

- **should propagate the error rather than return an empty list when the request times out** — marginally higher value than the rest of this group because the natural wrong fix here is `except: return []`.
- **should propagate the error when the backend returns a non-2xx.**
- **should attach an `Authorization: Bearer <key>` header when an api key is set, and omit it otherwise.**
- **should POST to `{base_url}/api/embed` with the configured embed model and the texts under `input`** — the key is `input` (not `prompt`, not `texts`) and the endpoint is `/api/embed` (not `/api/embeddings`) — both are the batch-API forms and both are wire contract.
- **should pass the configured timeout to the underlying client, defaulting to 120.0.**

### ABC conformance — `LLMClient` / `Embedder`

- **should be usable through the ABC without any caller naming an Ollama concept** — assert `isinstance` for both and that neither ABC's module-level source mentions "ollama". Low value on its own, but it is the executable form of the guard both specs lead with, and it is three lines.

## Gotchas

**No network in tests, ever.** Both specs are explicit that the real backend is reached over an SSH tunnel in dev. A test that forgets the monkeypatch will not fail fast — it will hang until the 120-second default timeout expires, then fail with a `ConnectError` that looks like a legitimate assertion about error propagation. If a transport test is mysteriously slow, the patch target is wrong. Consider asserting in the shared fixture that the factory was actually called at least once.

**Patch the module path, not `httpx`.** Both clients do `import httpx` and call `httpx.AsyncClient(...)` at call time, so patching through the module works — but note this mutates the shared `httpx` module object reached through `src.llm.client`, not a per-module alias. `monkeypatch` restores it, so it is safe, but two clients patched in one test will collide. Patch one client per test.

**Batching semantics are the subtle part.** Three distinct behaviours hide behind "batching" and each needs its own assertion: (a) empty input short-circuits with *no* HTTP call; (b) all texts go in *one* request; (c) vectors come back *positionally aligned* with inputs. Count-only assertions miss (c) entirely — use distinguishable vectors (`[1.0]`, `[2.0]`, `[3.0]`) so a reordering is visible. Also note that `Reasoner` calls `embed([query])` and takes `[0]`, so the single-element batch is the hottest path in production and deserves an explicit case.

**High-value vs. loud-failure filler.** The `test-philosophy` rule sorts these cases sharply:

- *High value (silent failure, no crash):* every case under **`OllamaClient.generate` — response parsing**, and every case under **`OllamaEmbedder.embed` — response validation**. These are the two surfaces where a missing `raise` converts a backend failure into an empty string or a corrupt vector list. The empty-input short-circuit and the positional-ordering case also belong here.
- *Filler (fails loudly already):* bad URL, HTTP 500, connection refused, header presence, timeout plumbing. Write them because they are three lines each on top of fixtures you already need, but do not treat the file as covered because they pass.

**The generator's guards do not exist yet — expect red.** Every case in the first group will fail on first run. That is the deliverable, not a setup error: the implementation change is to add the embedder's guard discipline to `generate` before merging. Follow the embedder's precedent — raise `ValueError` with a message naming the client and the specific defect — so both boundaries fail the same way and callers can catch one type.

**Dimension stability is only checked *within* a call.** The embedder compares vector lengths against each other inside a single batch. Nothing checks the result against the configured model's expected dimension or against previous calls, so two separate `embed` calls returning internally-consistent but mutually different dimensions both pass. Spec 05's guard is therefore only half-enforced here; the other half lives at the pgvector column, where a mismatch fails loudly on insert. Worth a comment in the test file so the gap is deliberate — and if the store ever stops enforcing it, this becomes a silent hazard needing a real test.

**`request=None, response=None` on `httpx.HTTPStatusError`.** Both existing delivery tests construct it that way. It is technically off-spec for `httpx` but works, and it keeps the fakes trivial. Match it rather than building real `Request`/`Response` objects.

## Seam in place — supersedes the Instantiation section above

The seam this plan asked for is present on both classes:

```python
OllamaClient(base_url, model, api_key=None, timeout=120.0, transport=None)
OllamaEmbedder(base_url, model, api_key=None, timeout=120.0, transport=None)
```

`transport: httpx.AsyncBaseTransport | None` is threaded straight into `httpx.AsyncClient(timeout=..., transport=...)` in both `generate` and `embed`.

**This replaces the `FakeAsyncClient` / `FakeResponse` monkeypatch pattern the Instantiation section above describes.** Do not hand-write a stand-in client; pass `httpx.MockTransport` and return real responses:

```python
def handler(request: httpx.Request) -> httpx.Response:
    calls.append(request)
    return httpx.Response(200, json={"response": "text"})

client = OllamaClient("http://h", "m", transport=httpx.MockTransport(handler))
```

What this changes about authoring the cases:

- **Response bodies** are real `httpx.Response` objects, so `raise_for_status` and `.json()` behave exactly as in production — no approximation to drift from.
- **The timeout case gains fidelity.** The Gotchas note that a hand-written fake could only raise a timeout from `raise_for_status` rather than from the request itself; a handler that raises `httpx.ReadTimeout` reproduces the real path.
- **`httpx.HTTPStatusError(request=None, response=None)` is no longer needed** — return a real non-2xx response and let `raise_for_status` construct the error.
- **Request assertions** read off the recorded `httpx.Request`: `request.url`, `request.headers`, and `json.loads(request.content)` cover the endpoint, the conditional bearer header, and the body shape.
- **The timeout-plumbing case** is the one thing `MockTransport` cannot observe, since it bypasses the timeout. Assert `client._timeout` directly, or drop the case as loud-failure filler.
- Everything in the two **response-validation** groups is unchanged in substance — only how the response is supplied changes.

**Still red:** the generator's response-parsing group. The seam task deliberately changed no behaviour, so `generate` still returns whatever the decoded body holds under its text key, with none of the validation its sibling embedder performs. Adding that guard is its own task; these tests land with it, not with the seam.

### Historical — the friction this replaced

`base_url`, `model`, `api_key` and `timeout` were already constructor parameters and cost a test nothing. The friction was that both `OllamaClient.generate` and `OllamaEmbedder.embed` built their `httpx.AsyncClient` inside the call, with no client and no `transport=` parameter — and the one thing every test in this plan must vary is precisely the response body and the transport error.

So each case can only reach its subject by monkeypatching the module's `httpx.AsyncClient` symbol, which is what `tests/delivery/test_telegram_client.py` and `tests/delivery/test_changelog_client.py` already do, at the cost of a hand-written fake client/response pair per module. That fake then has to re-implement the async-context-manager protocol, `post`, `raise_for_status` and `json` — none of which is the behavior under test.

**The refactor and the post-refactor API:**

Accept an injected client or a transport parameter on both classes, e.g.

```python
OllamaClient(base_url, model, api_key=None, timeout=120.0, transport=None)
OllamaEmbedder(base_url, model, api_key=None, timeout=120.0, transport=None)
```

passed straight through to `httpx.AsyncClient(timeout=..., transport=transport)`. Tests then hand in `httpx.MockTransport(handler)` and get **real** `httpx.Response` objects — real `raise_for_status`, real `.json()`, real `httpx.HTTPStatusError` / `ReadTimeout` / `ConnectError` semantics — instead of a hand-rolled stand-in whose fidelity is itself a source of false passes. The Gotchas section above notes two places where the fake's approximation bites (the timeout raised from `raise_for_status` rather than from `post`, and `HTTPStatusError(request=None, response=None)`); both disappear with a transport parameter.

Guard: `transport` is keyword-with-default-`None`, so the production wiring in `src/main.py` and the four `scripts/*` composition roots is unchanged, and `httpx` uses its own default transport exactly as today. This is orthogonal to the missing empty-response guard in `OllamaClient.generate` — that is a behavior change the test cases themselves drive, not part of this refactor. Consider whether `TelegramClient`, `ChangelogClient` and `GitHubReleaseClient` should take the same parameter in the same pass, since all five share the construct-client-inline shape and two of them already carry the hand-written fake.
