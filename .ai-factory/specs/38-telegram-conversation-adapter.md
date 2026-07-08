# 15.3 — Telegram conversation adapter (inbound)

**Phase:** 15 — Conversational surface. Depends on 15.1 (the conversation path), Phase 7 (`Reasoner.answer`), 9.2 (`TelegramClient`, to reply).

## Current state

9.2 sends *to* Telegram (outbound only). The conversation surface (15.1) is an HTTP `POST /ask` endpoint — reachable by a client that calls it directly, but nothing lets a person ask a question **via Telegram**, the channel Herald already delivers narration through.

## Change

Add an inbound Telegram receiver that treats an incoming message as a question and replies with the reasoner's answer.

- `src/ingestion/telegram_webhook.py` (or a sibling router) — `POST /webhooks/telegram`:
  1. verify Telegram's own secret-token header (`X-Telegram-Bot-Api-Secret-Token`, configured via `Settings`) — **not** GitHub's HMAC scheme, a distinct mechanism;
  2. parse the incoming update into a message text and chat id; parse any repo scope mentioned in the message text (best-effort, e.g. an explicit `repo:org/name` prefix);
  3. call the conversation path (`Reasoner.answer`, via 15.1's existing wiring or `Reasoner` directly) with the message text and parsed scope;
  4. `TelegramClient.send` (9.2) the answer back to the originating chat.
- Wired at the composition root alongside the existing GitHub webhook router.

## Files & types

- new `src/ingestion/telegram_webhook.py` (or equivalent router module)
- edit `src/core/config.py` (`telegram_webhook_secret`)
- edit `main.py` (mount the new router)

## Guards

- Authenticated via Telegram's secret-token header, verified before any parsing — same "verify before parse" discipline as 2.1's HMAC check, different mechanism.
- **Thin adapter** — holds no reasoning of its own; delegates entirely to `Reasoner.answer`, exactly like 15.1's HTTP surface.
- Reuses `TelegramClient` (9.2) for the reply — no second Telegram-sending code path.

## Verification

- A message sent to the bot → the reasoner's answer is sent back to the same chat.
- An update with a missing or incorrect secret-token header → rejected, no processing.
- A message with an explicit repo scope → the answer is scoped to that project.
