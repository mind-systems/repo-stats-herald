# 9.3 — Telegram delivery service

**Phase:** 9 — Delivery & routing. Depends on 9.2 (the client) and 9.1 (the delivery plan). Closes the phase: the reusable Telegram delivery step. It has **no per-push trigger** — delivery is driven by the report cadence (Phase 10) and the staging/release milestones (Phase 11), never by an arbitrary push.

## Current state

Task 9.1 resolves a `DeliveryPlan` (branch role + release flags) but leaves the channel fields for this task. 9.2 gives a `TelegramClient`. Under Herald's cadence model a served push is **memory-only** — episodic always, semantic on the canonical ref — and is never reported per push; nothing here is wired into ingestion. There is no org→channel map and no delivery step. The first live caller of the delivery step is the daily report (Phase 10); the release path (Phase 11) is the second.

## Change

Build the reusable Telegram delivery mechanism: resolve the org's channel into the plan, and send an already-finished note to it. This is transport — it takes a note string, not a change; the localizer/narration that produce the note are the caller's concern (the report builder in Phase 10, the release builder in Phase 11).

- Extend `src/core/config.py` `Settings` with `telegram_channels: Annotated[dict[int, str], NoDecode]` — a JSON `{"<org_id>": "<chat_id>"}` map parsed by the **existing** `_parse_json_dict` validator (add `telegram_channels` to its field list), exactly as `github_org_logins: dict[int, str]` is parsed today (`src/core/config.py:26,42`); do **not** invent a delimited `org:chat` format. Keys are the **numeric org id** (`PushEvent.org_id: int`); values are the chat-id **string** (e.g. `"-100123"`, negative for channels), never a login.
- Extend `DeliveryPlanResolver` (9.1): fill `DeliveryPlan.telegram_channel: str | None` (the org's chat-id string from the map, or `None`) and `DeliveryPlan.language: str` — the lowercase code the channel delivers in, default `"ru"` (the same lowercase form `Reasoner.narrate`'s `lang` and the localizer's language keys use, 8.1/8.2 — never `"RU"`, so `plan.language` feeds them directly).
- `src/delivery/service.py` — `DeliveryService.deliver(plan: DeliveryPlan, note: str) -> None`: when `plan.telegram_channel` is set, `TelegramClient.send(plan.telegram_channel, note)`; otherwise log "no channel for org" and do nothing. A single concrete class — no ABC/registry (a second delivery backend is not a current concern).

## Files & types

- edit `src/core/config.py` (`telegram_channels`), `src/routing/models.py`/`resolver.py` (`DeliveryPlan.telegram_channel`, `language`)
- new `src/delivery/service.py` (`DeliveryService`)
- **not** edited: `src/ingestion/router.py` — this task adds no per-push delivery.

## Guards

- **No per-push delivery.** This task does not touch `src/ingestion/router.py`; a served push stays memory-only. `DeliveryService.deliver` has no Phase-9 caller — the daily report (Phase 10) is the first.
- **Numeric org-id key** — a str/int key mismatch would silently resolve every org to `None` (no delivery) or the wrong chat, with no crash. Mandatory test: a numeric `org_id` present in the map resolves to its chat id; an org absent from the map resolves to `None`.
- **Unmapped org → nothing sent, logged** — never posts to a wrong chat, never crashes. Mandatory test over a mocked `TelegramClient`: `plan.telegram_channel` set → `send` called exactly once with `(channel, note)`; `plan.telegram_channel is None` → `send` NOT called.
- Language defaults to the lowercase `"ru"` (a configured default, per `docs/behavior/delivery.md`) — the same code `narrate` and the localizer use, so `plan.language` feeds them without a case mismatch.
- The map is read through `Settings`, not inline.
- `DeliveryService` is one concrete class — the version header and the GitHub-release / app-changelog channels are Phases 11/12.

## Verification

- `DeliveryService.deliver(plan_with_channel, "note")` → `TelegramClient.send(channel, "note")` called once.
- `DeliveryService.deliver(plan_without_channel, "note")` → logged, `send` not called.
- `telegram_channels` parsed with a numeric org id → `resolve` fills `telegram_channel` for that org; an unmapped org → `telegram_channel is None`.
