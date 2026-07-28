# Plan: 9.2 — Telegram client

## Context
Add the outbound Telegram Bot API boundary: a `TelegramClient.send(chat_id, text)` that posts plain-text `sendMessage` calls over httpx, chunking any message beyond 4096 chars into ordered parts whose concatenation equals the original. Transport discipline mirrors `OllamaClient` (bounded timeout, `raise_for_status`).

## Settings
- Testing: yes (mandatory chunking test over a mocked transport, per spec)
- Logging: minimal
- Docs: no

## Tasks

### Phase 1: Config

- [x] **Task 1: Add `telegram_bot_token` to `Settings`**
  Files: `src/core/config.py`, `.env.example`
  Add `telegram_bot_token: str` to `Settings` (required, no default, mirroring the existing required `github_webhook_secret: str`). Add a `TELEGRAM_BOT_TOKEN=` entry to `.env.example` with a one-line comment ("Telegram Bot API token; value set per environment, never committed"). Token stays env-only — never referenced literally in code, never logged.

- [x] **Task 2: Keep the existing suite green under the new required field** (depends on Task 1)
  Files: `tests/conftest.py`, `tests/routing/test_role_for_branch.py`
  A new required `Settings` field breaks every test that materializes `Settings` without a token — both via `get_settings()` and via direct construction. There is no `.env` to backfill it (`Settings` reads `env_file=".env"`; only the git-ignored `.env.dev` exists locally), so both sites must supply the token explicitly:
  - `tests/conftest.py`: in the `webhook_secret_env` fixture (which already `monkeypatch.setenv`s the other required config before `get_settings.cache_clear()`, covering the `client` fixture → `app` lifespan → `get_settings()` path), add `monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-telegram-token")`.
  - `tests/routing/test_role_for_branch.py:25`: this test constructs `Settings` directly (`Settings(github_webhook_secret="x")`) and does **not** use that fixture, so it would raise a `ValidationError` for the missing field. Change it to `Settings(github_webhook_secret="x", telegram_bot_token="x")`.

  A repo-wide check for direct `Settings(` construction outside `get_settings()` found exactly this one test site, so these two edits close the gap. Do not change unrelated fixtures.

### Phase 2: Telegram client

- [x] **Task 3: Create the `delivery` feature package** (depends on Task 1)
  Files: `src/delivery/__init__.py`
  Add an empty `src/delivery/__init__.py` to establish the new feature package (the same convention as existing feature packages under `src/`).

- [x] **Task 4: Implement `TelegramClient` with plain-text chunked send** (depends on Task 3)
  Files: `src/delivery/telegram.py`
  Add a module-level constant `TELEGRAM_MESSAGE_LIMIT = 4096` (Telegram's per-message character limit). Add class `TelegramClient`:
  - `__init__(self, token: str, timeout: float = 30.0) -> None` — store the token and timeout as private attributes; take the token as a primitive (mirrors `OllamaClient.__init__` taking `base_url`/primitives, wired at the composition root). Never read env here.
  - A private character-boundary splitter, e.g. `_chunks(text: str) -> list[str]`, returning `≤ TELEGRAM_MESSAGE_LIMIT`-length parts sliced on the character boundary, in order, such that `"".join(_chunks(text)) == text` exactly (no loss, no duplication, no reordering). For a `text` at or under the limit, return `[text]` (a single part) — including the empty string, so `send` still posts once.
  - `async def send(self, chat_id: str, text: str) -> None` — open **one** `async with httpx.AsyncClient(timeout=self._timeout) as client:` for the whole send (one connection pool, not a fresh client per chunk), then for each chunk in order `await client.post(...)` to `https://api.telegram.org/bot{token}/sendMessage` with JSON body `{"chat_id": chat_id, "text": chunk}` — plain text, **no `parse_mode`**. Call `response.raise_for_status()` after each post so a non-2xx (e.g. a bad token → 401/404) or a transport error raises, exactly as `OllamaClient.generate` does. Send parts sequentially (await each before the next) so ordering is preserved; never truncate. Keep all HTTP/URL specifics inside this class (encapsulation).

### Phase 3: Chunking test (mocked transport)

- [x] **Task 5: Pin the mandatory chunking test over a mocked transport** (depends on Task 4)
  Files: `tests/delivery/__init__.py`, `tests/delivery/test_telegram_client.py`
  Add an empty `tests/delivery/__init__.py`, mirroring existing `tests/<feature>/__init__.py` packages. Write async tests (the suite uses `pytest-asyncio`) that mock the transport by capturing POST bodies — do **not** hit the network. Recommended mechanism: `monkeypatch` `src.delivery.telegram.httpx.AsyncClient` with a fake async-context-manager class whose `post(url, json=...)` records `(url, json)` into a shared list and returns a stub response with a no-op `raise_for_status()`. Cover:
  - **Single short message:** `send("chat", "hello")` records exactly one POST, `json["chat_id"] == "chat"`, `json["text"] == "hello"`, URL ends with `/bot<token>/sendMessage`, and no `parse_mode` key is present in the body.
  - **Over-length message → ordered parts (the silent-failure guard):** build a `text` longer than `4096` (e.g. `4096 * 2 + 123` chars, ideally with varied content so a reorder would be detectable); assert every captured `text` part is `≤ 4096`, `len(parts) >= 3`, and `"".join(captured_texts) == text` exactly (no char lost, no duplication, order preserved).
  - **Bad token raises:** configure the fake response's `raise_for_status` to raise `httpx.HTTPStatusError` (simulating a 401/404); assert `send(...)` propagates it and does not swallow it.
