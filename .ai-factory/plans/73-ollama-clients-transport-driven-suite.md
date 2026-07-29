# Test Plan: Ollama clients — transport-driven suite

## Context
`src/llm/embedder.py` (`OllamaEmbedder`) has no tests, yet a wrong, missing, or reordered vector poisons retrieval ranking with no crash. This plan covers the embedder's response validation, its batching contract, and its request-composition/transport plumbing, plus the ABC conformance guard both boundaries lead with. All cases drive through the injected `httpx.MockTransport` seam with real `httpx.Response` objects — never the network, never a hand-written client stand-in.

> DEVIATION: plan-line said "request composition and transport failure for **both** clients" / files show `tests/llm/test_client.py` already fully covers `OllamaClient` (response parsing, transport, request composition, timeout plumbing), landed by 23.5 together with the generator-guard fix / this entry does **not** re-specify or duplicate the client suite. It adds the missing embedder suite (the actual gap) and the shared ABC-conformance guard. The `OllamaClient` guards are also already implemented in `src/llm/client.py`, so the generator response-parsing group named as out-of-scope is done — confirmed against source, not assumed.

## Settings
- Testing: yes
- Logging: minimal
- Docs: no

## Test Command
`uv run pytest tests/llm/test_embedder.py`

## Target Spec File
`tests/llm/test_embedder.py`

## Fixture note (setup, not a task)
`tests/llm/conftest.py` currently exposes only `make_client` (for `OllamaClient`). Add a sibling `make_embedder(handler, **kwargs) -> (OllamaEmbedder, list[httpx.Request])` fixture that mirrors it exactly: wrap the caller's `handler` in a recording handler that appends each `httpx.Request` to a `calls` list, construct `OllamaEmbedder(base_url, model, transport=httpx.MockTransport(recording_handler), **kwargs)` defaulting `base_url`/`model` to the module constants, and return `(embedder, calls)`. Use distinguishable one-dimensional vectors (`[1.0]`, `[2.0]`, `[3.0]`) in fixtures so a reordering is visible. Never construct the embedder without the transport — a missed transport reaches the SSH tunnel and hangs for the full 120s timeout before failing like a real error assertion.

## Tasks

### Phase 1: OllamaEmbedder — the embedder suite

- [x] **Task 1: `OllamaEmbedder.embed` — batching contract**
  Files: `tests/llm/test_embedder.py`
  Test cases:
  - `should return an empty list and issue no HTTP request when given an empty text list` — assert `result == []` AND the recorded-calls list is empty (the short-circuit at `if not texts: return []` must run before the network is touched)
  - `should return one vector per input text in positional order for a well-formed batch` — send three texts, return `[[1.0], [2.0], [3.0]]`, assert exact order (guards the unstated index-alignment contract callers rely on)
  - `should send all texts in a single request rather than one request per text` — assert exactly one recorded call whose body `input` holds every text
  - `should embed a single-element batch in one request returning one vector` — the hottest production path (`Reasoner` calls `embed([query])[0]`)

- [x] **Task 2: `OllamaEmbedder.embed` — response validation**
  Files: `tests/llm/test_embedder.py`
  Test cases:
  - `should raise rather than return an empty list when the body lacks the 'embeddings' key` — body `{"model": "m"}`
  - `should raise rather than return an empty list when 'embeddings' is an empty list` — body `{"embeddings": []}` (parametrize with the missing-key case so a future split into `is None` / `== []` cannot drop a branch)
  - `should raise naming both counts when fewer vectors are returned than texts` — two texts, one vector back; assert both counts appear in the message
  - `should raise when more vectors are returned than texts` — one text, two vectors back
  - `should raise when any returned vector is empty` — body `{"embeddings": [[0.1, 0.2], []]}`; put the empty vector in a non-first position so an `if not embeddings[0]`-style guard would still fail
  - `should raise naming the conflicting dimensions when vectors have inconsistent lengths across the batch` — body `{"embeddings": [[0.1, 0.2], [0.3]]}`; assert membership of both numbers in the message (the impl formats a `set`, so ordering is not stable)
  - `should accept a batch where all vectors share one dimension` — the negative control; a `len(dimensions) >= 1`-style mistake would pass every failure case above and reject all valid input
  - Add a short comment near the dimension-consistency cases recording that this check is deliberately scoped to a single `embed` call only: nothing here checks vectors against the model's expected dimension or against a prior call — that half is enforced loudly at the pgvector column on insert. Keep the comment about behaviour only (no plan/spec/`.ai-factory` reference).

- [x] **Task 3: `OllamaEmbedder.embed` — request composition and transport**
  Files: `tests/llm/test_embedder.py`
  Test cases:
  - `should POST to {base_url}/api/embed with the configured model and the texts under 'input'` — assert `request.url` ends `/api/embed` (the batch endpoint, not `/api/embeddings`) and `json.loads(request.content) == {"model": MODEL, "input": [...]}` (key is `input`, not `prompt`/`texts`)
  - `should attach an 'Authorization: Bearer <key>' header when an api key is set`
  - `should omit the 'Authorization' header entirely when no api key is set` — parametrize `api_key=None` and `api_key=""` (empty string is falsy; pin it so a "tightening" to `is not None` can't ship `Bearer ` to the backend)
  - `should propagate the error rather than return an empty list when the request times out` — handler raises `httpx.ReadTimeout` (natural wrong fix here is `except: return []`)
  - `should propagate the error when the backend returns a non-2xx response` — handler returns `httpx.Response(500, ...)`; assert `httpx.HTTPStatusError`
  - `should carry the configured timeout on the client, defaulting to 120.0` — assert `embedder._timeout` for an explicit value and for the default (production never passes `timeout`, so `120.0` is the real value; `MockTransport` bypasses the timeout so it cannot be observed on the wire)

### Phase 2: Boundary ABC conformance

- [x] **Task 4: `LLMClient` / `Embedder` — ABC conformance**
  Files: `tests/llm/test_embedder.py`
  Test cases:
  - `should expose OllamaClient and OllamaEmbedder as instances of their model-agnostic ABCs` — assert `isinstance` for both concrete clients against `LLMClient` / `Embedder`
  - `should keep the ABC boundary free of any Ollama concept` — assert no vendor token appears in the abstract interface itself, scoping the source read to the ABC **class body** via `inspect.getsource(LLMClient)` / `inspect.getsource(Embedder)` — NOT the whole module file. Both `src/llm/client.py` and `src/llm/embedder.py` contain `"Ollama"` outside the ABC (the concrete class name and the error strings), so an `"ollama" not in open(file).read()` form fails red for the wrong reason; `inspect.getsource(cls)` returns only the ABC class body and is the correct, unambiguous scope. This is the executable form of the guard both boundaries lead with
