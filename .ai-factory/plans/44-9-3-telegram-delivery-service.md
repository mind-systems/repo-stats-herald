# Plan: 9.3 — Telegram delivery service

## Context
Add the reusable Telegram delivery step: an org→channel config map, channel/language fields on the delivery plan, and a `DeliveryService` that sends an already-finished note to the resolved channel (or logs when none resolves). Transport only — no per-push wiring; the first caller is the Phase 10 daily report.

## Settings
- Testing: yes
- Logging: minimal
- Docs: no

## Tasks

### Phase 1: Config & plan seam

- [x] **Task 1: Add `telegram_channels` to `Settings`**
  Files: `src/core/config.py`
  Add field `telegram_channels: Annotated[dict[int, str], NoDecode] = {}` alongside `github_org_logins` (line 27). Register it in the **existing** `_parse_json_dict` validator's decorator list (line 45) — add `"telegram_channels"` to `@field_validator("canonical_refs", "github_org_logins", ...)` — so it is parsed from a JSON `{"<org_id>": "<chat_id>"}` string exactly as `github_org_logins` is. Do NOT invent a delimited `org:chat` format and do NOT add a new validator. Keys are the numeric org id (`dict[int, str]` → pydantic coerces the JSON string keys to `int`); values are chat-id strings (e.g. `"-100123"`).

- [x] **Task 2: Add `telegram_channel` + `language` to `DeliveryPlan`**
  Files: `src/routing/models.py`
  Extend the frozen `DeliveryPlan` dataclass with `telegram_channel: str | None` and `language: str`. Give defaults (`telegram_channel: str | None = None`, `language: str = "ru"`) so existing constructions stay valid; `language` uses the lowercase `"ru"` form (the same code `Reasoner.narrate` and the localizer consume — never `"RU"`).

- [x] **Task 3: Fill the channel/language fields in `DeliveryPlanResolver`** (depends on Task 1, Task 2)
  Files: `src/routing/resolver.py`
  In `resolve`, look up the channel via `self._settings.telegram_channels.get(org_id)` (numeric org-id key → chat-id string, or `None` when unmapped) and pass it as `telegram_channel`. Set `language="ru"` (default the channel delivers in; keep it a named constant or literal consistent with the lowercase form). Do not read env directly — the map comes only through the injected `Settings`.

### Phase 2: Delivery service

- [x] **Task 4: Add `DeliveryService`** (depends on Task 2)
  Files: `src/delivery/service.py`
  New single concrete class — no ABC/registry. Constructor injects a `TelegramClient` (the public class from `src/delivery/telegram.py`). `async def deliver(self, plan: DeliveryPlan, note: str) -> None`: when `plan.telegram_channel` is set, `await self._client.send(plan.telegram_channel, note)`; otherwise log (module logger `logging.getLogger(__name__)`, `logger.info`) that there is no channel for the org and do nothing — never post to a wrong chat, never crash. Follow the module-logger pattern used in `src/reasoning/reasoner.py`. Transport only: takes a note string, does not build or localize it.

### Phase 3: Tests

- [x] **Task 5: Resolver channel/language tests** (depends on Task 3)
  Files: `tests/routing/test_role_for_branch.py` (or a new `tests/routing/test_delivery_channel.py`)
  Pin the numeric-org-id guard: build `Settings(github_webhook_secret="x", telegram_bot_token="x", telegram_channels={1: "-100123"})` and assert `resolve(org_id=1, ...).telegram_channel == "-100123"` (numeric key resolves to its chat id) and `resolve(org_id=2, ...).telegram_channel is None` (unmapped org → `None`). Assert `plan.language == "ru"`. Also assert the JSON-string parse path yields `int` keys (e.g. construct `Settings` with `telegram_channels='{"1": "-100123"}'` and confirm `settings.telegram_channels == {1: "-100123"}`) so a str/int key mismatch cannot silently resolve every org to `None`.

- [x] **Task 6: `DeliveryService.deliver` dispatch tests** (depends on Task 4)
  Files: `tests/delivery/test_delivery_service.py`
  Over a mocked/async-stub `TelegramClient`: a plan with `telegram_channel` set → `send` called exactly once with `(channel, note)`; a plan with `telegram_channel is None` → `send` NOT called (and nothing raised). Use `pytest.mark.asyncio`/`asyncio` per the project's existing async-test convention.
