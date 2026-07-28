import logging

from src.delivery.telegram import TelegramClient
from src.routing.models import DeliveryPlan
from src.versioning.versioner import Version

logger = logging.getLogger(__name__)


class DeliveryService:
    """Sends an already-finished note to the channel resolved on a
    `DeliveryPlan` — transport only, it never builds or localizes the note
    itself. When the plan carries no channel (org unmapped), it logs and
    does nothing rather than guessing a destination."""

    def __init__(self, client: TelegramClient) -> None:
        self._client = client

    async def deliver(self, plan: DeliveryPlan, note: str, version: "Version | None" = None) -> None:
        if plan.telegram_channel is None:
            logger.info("no telegram channel resolved for this delivery, skipping")
            return
        text = f"{version}\n\n{note}" if version is not None else note
        await self._client.send(plan.telegram_channel, text)
