from abc import ABC, abstractmethod

import httpx


class Embedder(ABC):
    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class OllamaEmbedder(Embedder):
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

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        headers = {}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
            response = await client.post(
                f"{self._base_url}/api/embed",
                json={"model": self._model, "input": texts},
                headers=headers,
            )
            response.raise_for_status()
            body = response.json()

        embeddings = body.get("embeddings")
        if not embeddings:
            raise ValueError("Ollama embed response is missing 'embeddings'")
        if len(embeddings) != len(texts):
            raise ValueError(
                f"Ollama embed response returned {len(embeddings)} vectors for {len(texts)} inputs"
            )
        if any(not vector for vector in embeddings):
            raise ValueError("Ollama embed response contains an empty vector")

        dimensions = {len(vector) for vector in embeddings}
        if len(dimensions) > 1:
            raise ValueError(f"Ollama embed response returned mismatched vector dimensions: {dimensions}")

        return embeddings
