from src.delivery.service import DeliveryService
from src.routing.models import BranchRole, DeliveryPlan


class FakeTelegramClient:
    """Stub `TelegramClient` — records every `send(chat_id, text)` call."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def send(self, chat_id: str, text: str) -> None:
        self.calls.append((chat_id, text))


def _plan(telegram_channel: str | None) -> DeliveryPlan:
    return DeliveryPlan(
        branch_role=BranchRole.RELEASE,
        is_release=True,
        is_prerelease=False,
        telegram_channel=telegram_channel,
    )


async def test_deliver_sends_note_to_resolved_channel() -> None:
    client = FakeTelegramClient()
    service = DeliveryService(client)

    await service.deliver(_plan("-100123"), "note text")

    assert client.calls == [("-100123", "note text")]


async def test_deliver_skips_send_when_no_channel_resolved() -> None:
    client = FakeTelegramClient()
    service = DeliveryService(client)

    await service.deliver(_plan(None), "note text")

    assert client.calls == []
