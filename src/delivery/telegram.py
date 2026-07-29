import httpx

TELEGRAM_MESSAGE_LIMIT = 4096

_REDACTED_ENDPOINT = "https://api.telegram.org/bot<redacted>/sendMessage"


class TelegramSendError(Exception):
    """Signals that a `TelegramClient.send` call failed (non-2xx response or
    transport failure), carrying only a status code and a redacted endpoint —
    never the bot token or any `httpx` request/response object that exposes it."""

    def __init__(self, status_code: int | None) -> None:
        self.status_code = status_code
        self.endpoint = _REDACTED_ENDPOINT
        suffix = f" (status {status_code})" if status_code is not None else ""
        super().__init__(f"Telegram send failed for {_REDACTED_ENDPOINT}{suffix}")


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
                try:
                    response = await client.post(url, json={"chat_id": chat_id, "text": chunk})
                    response.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    status = exc.response.status_code if exc.response is not None else None
                except httpx.RequestError:
                    status = None
                else:
                    continue
                raise TelegramSendError(status)  # no active exception here → __context__ stays None
