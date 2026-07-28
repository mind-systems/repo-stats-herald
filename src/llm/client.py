from abc import ABC, abstractmethod

import httpx


class LLMClient(ABC):
    @abstractmethod
    async def generate(self, prompt: str) -> str: ...


class OllamaClient(LLMClient):
    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str | None = None,
        timeout: float = 120.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url
        self._model = model
        self._api_key = api_key
        self._timeout = timeout
        self._transport = transport

    async def generate(self, prompt: str) -> str:
        headers = {}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
            response = await client.post(
                f"{self._base_url}/api/generate",
                json={"model": self._model, "prompt": prompt, "stream": False},
                headers=headers,
            )
            response.raise_for_status()
            return response.json()["response"]
