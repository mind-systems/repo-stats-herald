## Code Review Summary

**Task:** 9.2 — Telegram client
**Plan:** `.ai-factory/plans/43-9-2-telegram-client.md`
**Spec:** `.ai-factory/specs/15-telegram-client.md`
**Files reviewed (in full):** `src/core/config.py`, `src/delivery/__init__.py`, `src/delivery/telegram.py`, `tests/conftest.py`, `tests/delivery/__init__.py`, `tests/delivery/test_telegram_client.py`, `tests/routing/test_role_for_branch.py`, `.env.example` — cross-checked against `src/llm/client.py`, `src/main.py`, `src/ingestion/router.py`, and every `get_settings()`/`Settings(` call site.
**Risk Level:** 🟢 Low

### What was verified

- **Full suite is green.** `uv run python -m pytest -q` → **112 passed**. The new `tests/delivery` (3 cases) and the updated `tests/routing/test_role_for_branch.py` pass.
- **Chunking invariants hold at every boundary.** Independently exercised `_chunks` at sizes `0, 1, 4095, 4096, 4097, 8192, 8315`: `"".join(parts) == original` exactly, every part `≤ 4096`, order preserved, and empty string → `[""]` (one post). No loss, no duplication, no reordering — the spec's silent-failure guard is satisfied by the impl, not just asserted in the test.
- **Transport discipline mirrors `OllamaClient`.** One `async with httpx.AsyncClient(timeout=self._timeout)` for the whole send, sequential `client.post(url, json=...)`, `response.raise_for_status()` after each post. Non-2xx / transport errors raise; no silent no-op. Body is `{"chat_id", "text"}` with **no `parse_mode`** — matches the plain-text mandate.
- **Config change is contained.** `telegram_bot_token: str` (required, no default) mirrors the existing `github_webhook_secret: str`. The required-field breakage analysis is complete: the only two `Settings` materialization paths — `get_settings()` (primed for tests via the `webhook_secret_env` fixture) and the one direct `Settings(...)` at `tests/routing/test_role_for_branch.py:25` — are both fixed. A repo-wide grep confirms no third live construction site (the `src/github/mirror.py:30` hit is a docstring). `.env.example` gains a no-value, per-environment `TELEGRAM_BOT_TOKEN=` entry consistent with `GITHUB_WEBHOOK_SECRET`.
- **Architecture/DI honored.** New `src/delivery/` feature package owns `TelegramClient`; token taken as a primitive in `__init__`, no env read in the class, HTTP/URL specifics encapsulated. Concrete wiring correctly deferred to a future composition root (not wired here — consistent with 9.3 being the first caller).

### Critical Issues

None.

### Minor Issues

None blocking. One cosmetic note, not a defect: the bad-token test constructs `httpx.HTTPStatusError("Unauthorized", request=None, response=None)`. Passing `request=None`/`response=None` is fine for raising in a stub, and the test correctly asserts the error propagates unswallowed; no change required.

## Deferred observations

- **Token-in-URL can leak through error logging (out of scope — future consumer boundary).** The Bot API embeds the secret in the path (`/bot{token}/sendMessage`), and `raise_for_status()` raises `httpx.HTTPStatusError` whose string form includes the request URL. `TelegramClient` itself never logs and never references the token literally, so the spec guard ("never logged") holds within this task. The risk lives at the error-logging boundary of a future caller (e.g. the delivery orchestrator / 15.x inbound adapter), which should scrub the token before logging Telegram transport errors. Already flagged in plan-review-1; carried forward unchanged.
- **4096 limit is UTF-16 code units, but chunking uses Python `len` (code points) — governing-spec decision, out of scope.** A message dense in astral-plane characters (emoji, some CJK extensions) can yield a part whose Python `len` ≤ 4096 yet exceeds Telegram's UTF-16 count, so the API 400s and `raise_for_status` raises (surfaced, not silent). The impl faithfully implements the spec as written ("character boundary"); flagging only so a future delivery-hardening pass can decide whether to measure in UTF-16 units. Already flagged in plan-review-2.

REVIEW_PASS
