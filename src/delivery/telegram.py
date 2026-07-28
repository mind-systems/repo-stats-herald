import httpx

TELEGRAM_MESSAGE_LIMIT = 4096


class TelegramClient:
    def __init__(self, token: str, timeout: float = 30.0) -> None:
        self._token = token
        self._timeout = timeout

    def _chunks(self, text: str) -> list[str]:
        if len(text) <= TELEGRAM_MESSAGE_LIMIT:
            return [text]
        return [
            text[i : i + TELEGRAM_MESSAGE_LIMIT]
            for i in range(0, len(text), TELEGRAM_MESSAGE_LIMIT)
        ]

    async def send(self, chat_id: str, text: str) -> None:
        url = f"https://api.telegram.org/bot{self._token}/sendMessage"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for chunk in self._chunks(text):
                response = await client.post(url, json={"chat_id": chat_id, "text": chunk})
                response.raise_for_status()
