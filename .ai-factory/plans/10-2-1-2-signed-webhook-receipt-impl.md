# Plan: 2.1.2 — Signed webhook receipt (impl)

## Context
Replace the logic-free `POST /webhooks/github` stub with real HMAC verify-before-parse, event-type branching, and payload→`PushEvent` mapping, turning 2.1.1's red contract tests green.

## Settings
- Testing: no
- Logging: minimal
- Docs: no

## Tasks

### Phase 1: Implement the webhook route

- [x] **Task 1: HMAC verify-before-parse of the raw body**
  Files: `src/ingestion/router.py`
  Change the handler `receive_github_webhook` to accept the FastAPI `Request` (`request: fastapi.Request`) so it can read the **raw** body as bytes: `body = await request.body()`. Read the secret from env only via `get_settings().github_webhook_secret` (import `from src.core.config import get_settings`; call it inside the handler at request time — the tests clear its cache per test, see `tests/conftest.py`). Compute the expected signature with the stdlib: `import hmac, hashlib`; `expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()`. Read the header `X-Hub-Signature-256` (exact name — matches the `sign` fixture and the spec; note the roadmap one-liner's shorthand "sha256=<hex> header" refers to this header). If the header is absent or `hmac.compare_digest(expected, header)` is false → return `Response(status_code=401)` immediately, **before any JSON parse** and with **no body** (the tampered-signature test asserts `"branch" not in response.text`). Use `hmac.compare_digest` (constant-time), never `==`.

- [x] **Task 2: Branch on X-GitHub-Event (non-push → 204)** (depends on Task 1)
  Files: `src/ingestion/router.py`
  Only after signature verification passes, read `request.headers.get("X-GitHub-Event")`. If it is not `"push"` (e.g. `ping`, `installation`) → return `Response(status_code=204)` with no body and no parse. Ordering matters: verify first (Task 1), then event-type gate, then parse (Task 3).

- [x] **Task 3: Parse the verified payload into `PushEvent` and return 200** (depends on Task 2)
  Files: `src/ingestion/router.py`
  Parse the already-read raw `body` with `json.loads(body)` (import `json`) and map the GitHub push payload onto the existing `PushEvent`/`PushCommit` value objects from `src/ingestion/models.py` (do not redefine them). Mapping, grounded in the `push_payload` fixture in `tests/conftest.py`:
  - `branch` = `payload["ref"]` with the `refs/heads/` prefix stripped (`ref.removeprefix("refs/heads/")` — yields `main`, `feature/x`).
  - `org_id` = `payload["organization"]["id"]` (numeric `int`, NOT the login), `org_login` = `payload["organization"]["login"]`.
  - `repo` = `payload["repository"]["name"]`.
  - `before` = `payload["before"]`, `after` = `payload["after"]`.
  - `commits` = a `tuple` of `PushCommit(sha=c["id"], message=c["message"], added=tuple(c["added"]), modified=tuple(c["modified"]), removed=tuple(c["removed"]), author=c["author"]["name"])` for each commit — note the payload's `id`→`sha` and nested `author.name`→`author`.
  Return the populated `PushEvent` as a 200 JSON response: `return JSONResponse(content=jsonable_encoder(event))` (import `JSONResponse` from `fastapi.responses`, `jsonable_encoder` from `fastapi.encoders`) so the frozen dataclass's tuples serialize to JSON arrays and the response is a uniform `Response` type across all three branches. Keep the handler thin: if it aids readability, factor signature-verification and payload-mapping into private module-level helpers (`_verify_signature`, `_parse_push_event`) within `router.py` — stay within this one file per the spec's file scope; do not add a new module. No new test surface — 2.1.1's suite is the contract.

### Phase 2: Verify green

- [x] **Task 4: Run the contract suite** (depends on Task 3)
  Files: `tests/ingestion/test_webhook_contract.py` (run only, do not edit)
  Run `uv run pytest tests/ingestion/test_webhook_contract.py` and confirm all five tests pass: valid signed push → 200 + populated `PushEvent` (int `org_id`, `org_login`, commit fields); `refs/heads/feature/x` → `branch` `feature/x`; tampered signature → 401 with no `branch` in body; absent signature → 401; `X-GitHub-Event: ping` → 204.
