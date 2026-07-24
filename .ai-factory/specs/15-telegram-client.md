# 9.2 — Telegram client

**Phase:** 9 — Delivery & routing. The outbound boundary to Telegram.

## Current state

The narration (Phase 8) produces prose, but nothing sends it anywhere. `Settings` has no Telegram token (`TELEGRAM_BOT_TOKEN` is a target config, not yet read). There is no Telegram client.

## Change

Add a thin Telegram Bot API client, behind a boundary so the delivery backend could swap.

- Extend `src/core/config.py` `Settings` with `telegram_bot_token: str`.
- `src/delivery/telegram.py`:
  - `TelegramClient` — `send(chat_id: str, text: str) -> None`: `httpx` POST to `https://api.telegram.org/bot{token}/sendMessage` with `chat_id` and `text` as **plain text** (no `parse_mode`, so no formatting entity a chunk boundary could split). Mirror `OllamaClient`'s transport discipline — an `httpx.AsyncClient` with a bounded timeout and `response.raise_for_status()` so a non-2xx or transport error raises (`src/llm/client.py`).
  - Split a message longer than `TELEGRAM_MESSAGE_LIMIT = 4096` (Telegram's per-message character limit, a module-level constant) into ordered ≤-limit parts on the character boundary, sent in sequence; their concatenation equals the original exactly.
- Constructed at the composition root with the token from `Settings`.

## Files & types

- edit `src/core/config.py` (`telegram_bot_token`)
- new `src/delivery/__init__.py`, `src/delivery/telegram.py` (`TelegramClient`)

## Guards

- Token from env via `Settings` only; never in code, never logged.
- API/transport errors raise (non-200, transport) via `response.raise_for_status()`, mirroring `OllamaClient` — never a silent no-op. Messages are plain text (no `parse_mode`).
- Over-length messages are chunked in order, not truncated.
- **Chunking is a silent-failure surface** — a bug could drop, duplicate, or reorder a part with no exception. Pin a mandatory test over a **mocked transport** (captured POST bodies), written before the impl: a >4096-char message → ordered parts whose concatenation equals the original exactly (no loss, no duplication), sent in sequence.

## Verification

- `send(chat_id, "hello")` posts to a test chat.
- A >4096-char message → the mocked transport receives ordered parts, and `''.join(parts) == original` (no char lost, no duplication, order preserved).
- A bad token / unreachable API raises.
