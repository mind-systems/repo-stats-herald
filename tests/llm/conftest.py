from collections.abc import Callable

import httpx
import pytest

from src.llm.client import OllamaClient
from src.llm.embedder import OllamaEmbedder

BASE_URL = "http://ollama.internal"
MODEL = "qwen2.5"


@pytest.fixture
def make_client() -> Callable[..., tuple[OllamaClient, list[httpx.Request]]]:
    """Builds an `OllamaClient` driven through its injected `transport` seam
    rather than a hand-rolled stand-in. The caller supplies a `handler(request)
    -> httpx.Response`; every request the handler receives is recorded, so
    cases can assert on the wire contract (URL, headers, body) after the call
    via `request.url`, `request.headers`, and `json.loads(request.content)`.

    Any constructor keyword (`api_key`, `timeout`, `base_url`, `model`) can be
    overridden; unset ones default to `BASE_URL`/`MODEL` and the client's own
    defaults (notably `api_key=None`, `timeout=120.0`)."""

    def _make_client(
        handler: Callable[[httpx.Request], httpx.Response], **kwargs: object
    ) -> tuple[OllamaClient, list[httpx.Request]]:
        calls: list[httpx.Request] = []

        def _recording_handler(request: httpx.Request) -> httpx.Response:
            calls.append(request)
            return handler(request)

        base_url = kwargs.pop("base_url", BASE_URL)
        model = kwargs.pop("model", MODEL)
        client = OllamaClient(
            base_url,
            model,
            transport=httpx.MockTransport(_recording_handler),
            **kwargs,
        )
        return client, calls

    return _make_client


@pytest.fixture
def make_embedder() -> Callable[..., tuple[OllamaEmbedder, list[httpx.Request]]]:
    """Builds an `OllamaEmbedder` driven through its injected `transport` seam
    rather than a hand-rolled stand-in. The caller supplies a `handler(request)
    -> httpx.Response`; every request the handler receives is recorded, so
    cases can assert on the wire contract (URL, headers, body) after the call
    via `request.url`, `request.headers`, and `json.loads(request.content)`.

    Any constructor keyword (`api_key`, `timeout`, `base_url`, `model`) can be
    overridden; unset ones default to `BASE_URL`/`MODEL` and the embedder's
    own defaults (notably `api_key=None`, `timeout=120.0`)."""

    def _make_embedder(
        handler: Callable[[httpx.Request], httpx.Response], **kwargs: object
    ) -> tuple[OllamaEmbedder, list[httpx.Request]]:
        calls: list[httpx.Request] = []

        def _recording_handler(request: httpx.Request) -> httpx.Response:
            calls.append(request)
            return handler(request)

        base_url = kwargs.pop("base_url", BASE_URL)
        model = kwargs.pop("model", MODEL)
        embedder = OllamaEmbedder(
            base_url,
            model,
            transport=httpx.MockTransport(_recording_handler),
            **kwargs,
        )
        return embedder, calls

    return _make_embedder
