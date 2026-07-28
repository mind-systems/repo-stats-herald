## Code Review Summary

**Plan:** `43-9-2-telegram-client.md` (task 9.2 — Telegram client)
**Files Reviewed:** plan + governing spec (`.ai-factory/specs/15-telegram-client.md`), `ROADMAP.md` line 92, `src/core/config.py`, `src/llm/client.py`, `tests/conftest.py`, `tests/routing/test_role_for_branch.py`, `.env.example`, `docs/behavior/delivery.md`
**Risk Level:** 🟡 Medium

### Context Gates
- **Architecture (`ARCHITECTURE.md` / project CLAUDE.md):** PASS. The plan honors the feature-modular DI pattern — new `src/delivery/` package owning its `TelegramClient`, token taken as a primitive in `__init__` (mirrors `OllamaClient`), concrete wiring deferred to the composition root, HTTP details encapsulated in the class. Depends on `core/` only. Aligned.
- **Rules (`.ai-factory/RULES.md`):** PASS. File is intentionally empty; no counter-defaults to check.
- **Roadmap (`ROADMAP.md` line 92 → spec `15-telegram-client.md`):** PASS on alignment. The plan faithfully implements the contract line and the spec: `telegram_bot_token`, `src/delivery/telegram.py`, `TELEGRAM_MESSAGE_LIMIT = 4096`, plain-text `sendMessage` (no `parse_mode`), ordered chunking with `join == original`, `raise_for_status` discipline, and the mandatory mocked-transport chunking test the spec explicitly pins. No skill-context override file present.

### Critical Issues

**1. Task 2 does not keep the suite green — `tests/routing/test_role_for_branch.py:25` breaks under the new required field.**
Task 2's stated purpose is "Keep the existing suite green under the new required field," and it patches only the `webhook_secret_env` fixture in `tests/conftest.py`, with the explicit instruction "Do not change unrelated fixtures." But `test_role_for_branch.py` does **not** use that fixture — it constructs `Settings` directly:

```python
resolver = DeliveryPlanResolver(Settings(github_webhook_secret="x"))
```

Today `github_webhook_secret` is the only required field, so this call succeeds. Once `telegram_bot_token: str` (required, no default) is added, this line raises a pydantic `ValidationError` for the missing field. There is no `.env` to backfill it: `Settings` reads `env_file=".env"`, and only `.env.dev` exists locally (and both are git-ignored), so nothing supplies `TELEGRAM_BOT_TOKEN` during a plain/CI test run. Result: `test_resolve_derives_flags_from_role` goes red, and an implementer following the plan literally (Files: only `tests/conftest.py`; "do not change unrelated fixtures") would leave it red — defeating Task 2 and failing the downstream verify/review.

Fix: extend Task 2's scope to also provide the token where `Settings` is constructed directly — update `tests/routing/test_role_for_branch.py:25` to `Settings(github_webhook_secret="x", telegram_bot_token="x")` (add the file to Task 2's `Files` list). A repo-wide check for direct `Settings(` construction found exactly this one test site outside `get_settings()`, so that single addition closes the gap.

### Positive Notes
- The chunking invariant is specified with real rigor — `"".join(_chunks(text)) == text`, `≤ limit` parts, order preserved, and the `[text]`/`[""]` single-post edge — matching the spec's silent-failure guard, and the test is pinned before impl.
- Transport discipline is correctly modeled on `OllamaClient.generate`: bounded-timeout `AsyncClient`, `raise_for_status` after each post, no silent no-op, plain text (no `parse_mode`).
- Task 5 mocks the transport by monkeypatching `src.delivery.telegram.httpx.AsyncClient`, which correctly targets the module-local `httpx` reference the impl will use; `asyncio_mode = "auto"` means the async tests need no per-test decorator, consistent with the existing suite.
- The `.env.example` addition with a no-value, per-environment comment matches the established convention for `GITHUB_WEBHOOK_SECRET`.

### Minor Issues (in-scope, worth tightening before implementation)

**2. Task 4 wording invites a new `AsyncClient` per chunk.** "for each chunk in order, `await` an `httpx.AsyncClient(timeout=self._timeout)` POST" reads as opening a fresh client inside the per-chunk loop. Preferred: open one `async with httpx.AsyncClient(...)` and issue the sequential posts inside it (one connection pool for the whole `send`). Behaviorally equivalent under the mocked test, but a minor efficiency/clarity point the plan should pin so the implementer doesn't hard-code the wasteful form.

## Deferred observations
- Affects: task 15.3 (Telegram conversation adapter) / any future caller that logs `TelegramClient` errors — The Bot API embeds the secret token in the request URL (`/bot{token}/sendMessage`). `raise_for_status()` raises `httpx.HTTPStatusError` whose string form includes that URL, so the token can leak into logs or tracebacks if an upstream catches and logs the exception. This client itself neither logs nor references the token literally, so the guard ("never logged") holds within this task's boundary; the concern lives at the error-logging boundary of a future consumer and is inherent to Telegram's URL-in-path design (the spec deliberately mandates the `raise_for_status` mirror of `OllamaClient`). Flagging so the inbound adapter / delivery orchestrator scrubs the token before logging Telegram transport errors.
