# Plan: 2.1.1 — Push-event models + webhook contract (red tests)

## Context
Lay the ingestion feature's entry surface — immutable `PushCommit`/`PushEvent` value objects, a `github_webhook_secret` setting, and a STUB `POST /webhooks/github` route wired into the app — then pin its security contract with red tests written against the stub, ahead of the verify/parse implementation (2.1.2).

## Settings
- Testing: yes (red contract tests over the stub are this task's core deliverable)
- Logging: minimal
- Docs: no

## Notes for the implementer
- **Tests-first / red, not green.** This task adds NO signature-verification or payload-parsing logic. The tests MUST fail against the stub — and fail for the right reason (missing logic → the stub's `501`), never an import/fixture error or an unrelated crash. 2.1.2 turns them green; never weaken a test to make it pass here.
- **No test harness exists yet.** The repo has no `pytest`, no `tests/` tree, and no test target — Phase 3 bootstraps all of it. `.gitignore` already carries `.pytest_cache/`/`.coverage` entries and `fastapi.testclient` imports cleanly, so no extra runtime deps beyond `pytest` are needed.
- **`src` must be importable from tests, or collection errors instead of failing red.** `pyproject.toml` has no `[build-system]`, so the project is not installed — `src` resolves only when the project root is on `sys.path`. The scripts get that today via the `-m` run form (`uv run python -m scripts.eval`), but `pytest`'s default (prepend) import mode puts only each test/conftest's basedir (`tests/`) on the path, never the root — so `from src.main import app` would raise `ModuleNotFoundError` at collection. Task 5 pins the root onto the path declaratively via `pythonpath = ["."]` so the harness works regardless of run form (`uv run pytest` or `python -m pytest`).
- **Follow the established value-object pattern** in `src/commits/models.py`: `@dataclass(frozen=True, slots=True)`, `tuple[...]` for collections. Match it exactly.
- **Stub returns `501`, does not raise.** Returning an explicit `501` (rather than raising `NotImplementedError`) keeps the red run clean — a raised exception surfaces through `TestClient` as a `500`/re-raised server error and muddies "failed for the right reason". The route reads NO settings and parses NO body in this task.

## Tasks

### Phase 1: Type surface & config

- [x] **Task 1: Ingestion package + push-event value objects**
  Files: `src/ingestion/__init__.py` (new), `src/ingestion/models.py` (new)
  Create the `src/ingestion/` feature package. In `models.py` define two immutable value objects following `src/commits/models.py`'s `@dataclass(frozen=True, slots=True)` pattern:
  - `PushCommit`: `sha: str`, `message: str`, `added: tuple[str, ...]`, `modified: tuple[str, ...]`, `removed: tuple[str, ...]`, `author: str`.
  - `PushEvent`: `org_id: int`, `org_login: str`, `repo: str`, `branch: str`, `before: str`, `after: str`, `commits: tuple[PushCommit, ...]`.
  These are the most-shared downstream types (2.2, 3.6, 4.2/4.3, 9.1…) — no methods, no parsing logic, just the frozen shape. `org_id` is `int` (the numeric GitHub org id), deliberately distinct from the `org_login` string.

- [x] **Task 2: Add `github_webhook_secret` to Settings**
  Files: `src/core/config.py`
  Add `github_webhook_secret: str` to `Settings` — a required field with **no default in code** (secret comes from env only; already documented in `.env.example`). Place it after the existing Ollama/SSH fields. Do not touch `get_settings()`. Nothing at import/composition time instantiates `Settings` today, so a required field introduces no boot regression; tests supply the value via env.

### Phase 2: Stub route & wiring

- [x] **Task 3: Stub webhook route** (depends on Task 1)
  Files: `src/ingestion/router.py` (new)
  Add an `APIRouter` exposing `POST /webhooks/github` that, for **every** request, returns an explicit `501` response (e.g. `fastapi.Response(status_code=501)`) — reachable but logic-free. It reads no headers, no body, and no `Settings`. This is the surface the red tests hit; 2.1.2 replaces the body with verify-before-parse logic. Keep the router thin (per ARCHITECTURE: routers are thin, wiring at the composition root).

- [x] **Task 4: Wire the router into the app** (depends on Task 3)
  Files: `src/main.py`
  Import the ingestion router and `app.include_router(...)` it at the composition root, alongside the existing `GET /health`. After this, `make run` still serves `/health` and `POST /webhooks/github` is reachable (returns `501`). No settings read, no dependency injection yet — that arrives with 2.1.2.

### Phase 3: Test harness & red contract tests

- [x] **Task 5: Bootstrap the pytest harness** (depends on Task 4)
  Files: `pyproject.toml`, `Makefile`, `tests/conftest.py` (new)
  - Add `pytest` as a dev dependency group in `pyproject.toml` (`[dependency-groups]` `dev = ["pytest"]`, picked up by `uv sync`) and a `[tool.pytest.ini_options]` block with `testpaths = ["tests"]` **and `pythonpath = ["."]`**. The `pythonpath = ["."]` entry is mandatory, not optional polish: without the project root on `sys.path`, `from src.main import app` in `conftest.py` raises `ModuleNotFoundError` at collection and every test errors instead of failing red against the `501` stub — defeating the task's central guard. It is declarative and survives a bare `pytest` invocation, so the harness does not depend on the run form.
  - Add a `test` target to the `Makefile` (`uv run pytest`) and to `.PHONY`.
  - In `tests/conftest.py` provide shared fixtures:
    - a fixed test webhook secret (a constant, e.g. `"test-webhook-secret"`);
    - a fixture that sets `GITHUB_WEBHOOK_SECRET` in the environment (via `monkeypatch.setenv`) **and clears the `get_settings` `lru_cache`** so the value 2.1.2 will read matches what the tests sign with;
    - a `TestClient` fixture over `src.main.app`;
    - a `sign(body: bytes) -> str` helper returning `"sha256=" + hmac.new(secret, body, sha256).hexdigest()` (the `X-Hub-Signature-256` value GitHub sends);
    - a valid GitHub `push` payload builder returning canonical JSON `bytes` — shape mirrors a real GitHub push: `organization.id` (numeric) + `organization.login`, `repository.name`, `ref = "refs/heads/main"`, `before`/`after` SHAs, and a `commits` list whose entries carry `id`/`message`/`added`/`modified`/`removed`/`author`. Use a distinctive numeric org id (e.g. `244165546`, the served org from 2.2) and a login string that is clearly NOT the id, so the "numeric not login" assertion has teeth.

- [x] **Task 6: Red contract tests over the stub** (depends on Task 5)
  Files: `tests/ingestion/__init__.py` (new, if package-style layout used), `tests/ingestion/test_webhook_contract.py` (new)
  Write tests that POST to `/webhooks/github` and assert the contract 2.1.2 must satisfy. All are RED now (stub returns `501`); each must fail only because the logic is absent. Cover exactly:
  - **Valid signature + `push` → 200 + populated `PushEvent`.** POST the valid payload with a correct `X-Hub-Signature-256` (from `sign`) and `X-GitHub-Event: push`; assert `200` and that the response reflects a populated event — specifically `branch == "main"` (proving `ref` `"refs/heads/main"` was stripped) and `org_id == 244165546` as the **numeric id** (asserting it equals the id and is NOT the `org_login` string). Assert commit fields are carried through (sha/message/added/modified/removed/author).
  - **`ref` → `branch` strip** — covered by the assertion above; if clearer, add a focused case posting `ref = "refs/heads/feature/x"` and asserting `branch == "feature/x"`.
  - **Tampered signature → 401.** Correct header name, wrong digest (e.g. sign a different body, or mutate one hex char); assert `401` and that nothing was parsed (no event body returned).
  - **Absent signature → 401.** POST the valid `push` payload with **no** `X-Hub-Signature-256` header at all; assert `401`. This is the explicit anti-hazard: a missing header must be rejected, never silently accepted — this case is the reason the task is split out, so it is mandatory and must not be conflated with the tampered case.
  - **Non-`push` event → 204.** POST a validly signed payload with `X-GitHub-Event: ping` (or another non-push value); assert `204` and no processing.
  Do not assert the internal `PushEvent` object identity — assert the observable HTTP contract (status + response shape). That is what 2.1.2 is bound to.

## Deferred observations
- Affects 2.1.2 (`specs/01-signed-webhook-receipt.md`): the valid-signature test reads `branch`/`org_id`/commit fields from the HTTP **response body**, so it binds 2.1.2 to echo the parsed `PushEvent` back in the `200` response. At this stage that echo is the only observable proof parsing worked, so it is a sound contract-test choice — but a production receiver normally returns a minimal `200` and hands the event to a pipeline. When the real downstream consumer lands, revisit whether the endpoint should still serialize the full event, or whether this observability hook should move to the pipeline seam, so the response shape is not frozen purely by a red test.
- `.env.dev` already carries `GITHUB_WEBHOOK_SECRET` (a real value), so making the field required-with-no-default introduces no regression for `make dev`/`make eval` (which instantiate `Settings` via `get_settings()`). No `.env.dev` change is owed.
