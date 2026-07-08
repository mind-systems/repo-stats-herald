# 2.1.2 — Signed webhook receipt (impl)

**Phase:** 2 — Ingestion & the event stream. Depends on 2.1.1 (the models, `Settings.github_webhook_secret`, the stub route, and its red tests). Second half of the webhook receipt milestone — turns 2.1.1's tests green.

## Current state

2.1.1 defines `PushEvent`/`PushCommit`, extends `Settings` with `github_webhook_secret`, and stubs `POST /webhooks/github` with red tests pinning its security contract. The stub itself raises/`501`s for every request — no HMAC verification, no event-type branch, no payload parsing exists yet.

## Change

Implement the webhook route so 2.1.1's red tests go green.

- `src/ingestion/router.py` — replace the stub `POST /webhooks/github` with real logic:
  1. read the **raw** request body (bytes) before any JSON parse;
  2. compute `hmac.new(secret, body, sha256)` and compare against the `X-Hub-Signature-256` header (`sha256=<hex>`) with `hmac.compare_digest`; on absence/mismatch → `401` and return, no parse;
  3. read `X-GitHub-Event`; if not `push` → `204` (ignored), no parse;
  4. parse the verified body into `PushEvent` (map GitHub payload → the model from 2.1.1; `ref` → `branch`, `org_id` numeric).

## Files & types

- edit `src/ingestion/router.py` (stub → real implementation)

## Guards

- Signature verified against the **raw** body **before** any JSON parsing; use `hmac.compare_digest` (constant-time).
- Missing/malformed/mismatched signature → `401`, nothing parsed, nothing logged as content.
- Non-`push` events → `204`, ignored (GitHub also sends `installation`, `ping`, etc.).
- Secret only from env via `Settings`; never in code.
- Turns 2.1.1's tests green — introduces no new test surface of its own beyond what 2.1.1 already pinned.

## Verification

- 2.1.1's red test suite passes green against this implementation.
- A request signed with the configured secret over a real GitHub `push` sample body → `200`, and the handler produces a populated `PushEvent` (org_id, repo, branch, commits).
- The same body with a tampered/absent `X-Hub-Signature-256` → `401`, no `PushEvent`.
- An `X-GitHub-Event: ping` request → `204`.
