# 2.1.1 — Push-event models + webhook contract (red tests)

**Phase:** 2 — Ingestion & the event stream. First task; the Ingest seam's entry point — models, security contract, and red tests, ahead of the implementation (2.1.2).

## Current state

`src/main.py` is a bare FastAPI app exposing only `GET /health`. Nothing types an incoming push, and the webhook endpoint doesn't exist — so its security contract (verify-before-parse, absent-signature handling) has no test pinning it down before the implementation is written. `src/core/config.py` `Settings` types the Ollama/SSH env only — it does not yet read `GITHUB_WEBHOOK_SECRET` (present in `.env.dev`/`.env.example`).

## Change

Define the push-event type surface, extend `Settings`, stub the webhook route, and pin its security contract with tests written against the stub — before any verification/parsing logic exists.

- `src/ingestion/models.py` — immutable value objects: `PushCommit` (`sha`, `message`, `added`, `modified`, `removed`, `author`), `PushEvent` (`org_id: int`, `org_login: str`, `repo: str`, `branch: str`, `before: str`, `after: str`, `commits: tuple[PushCommit,...]`) — the most-shared types downstream (2.2, 3.6's `on_push`, 4.2/4.3, 9.1...).
- Extend `src/core/config.py` `Settings` with `github_webhook_secret: str` (read from env, no default in code).
- `src/ingestion/router.py` — a STUB `POST /webhooks/github` that raises `NotImplementedError` (or returns `501`) for every request; wired into `main.py` (`app.include_router(...)`) at the composition root — the route exists and is reachable, so tests can hit it, but carries no logic yet.
- Write red tests against the stub, pinning the contract 2.1.2 must satisfy:
  - a validly signed `push` payload → `200` + populated `PushEvent`, with `ref`→`branch` stripped and `org_id` compared as the numeric id (never `org_login`);
  - a tampered or **absent** `X-Hub-Signature-256` header → `401`, nothing parsed (absent-signature silent-accept is the hazard this test exists to catch);
  - a non-`push` `X-GitHub-Event` → `204`.

## Files & types

- new `src/ingestion/__init__.py`, `src/ingestion/models.py` (`PushCommit`, `PushEvent`), `src/ingestion/router.py` (stub route)
- edit `src/core/config.py` (`Settings.github_webhook_secret`)
- edit `src/main.py` (include router)
- new test file(s) covering the contract above, run against the stub (red)

## Guards

- Tests-first: this task adds no verification/parsing logic — 2.1.2 turns these tests green, never the reverse.
- The absent-signature branch is explicitly asserted — silent-accept on a missing header is the specific hazard motivating this split.
- `PushEvent`/`PushCommit` immutable — the shared shape every downstream task depends on.
- Stub raises/`501`s rather than silently succeeding, so a red test fails for the right reason (missing logic), never a wrong one (crash elsewhere).

## Verification

- The test suite added here is red against the stub (fails only because the router has no logic yet — no import errors, no fixture errors).
- Compiles and boots (`make run` still serves `/health`); the stub route is reachable and returns `501`/raises for any request.
- Each of the three contract cases (valid signature, tampered/absent signature, non-`push` event) has a corresponding red test.
