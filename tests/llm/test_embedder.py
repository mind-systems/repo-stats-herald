import inspect
import json

import httpx
import pytest

from src.llm.client import LLMClient, OllamaClient
from src.llm.embedder import Embedder, OllamaEmbedder
from tests.llm.conftest import BASE_URL, MODEL

# --- batching contract -------------------------------------------------


async def test_embed_returns_empty_list_and_issues_no_request_for_empty_input(make_embedder) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"embeddings": [[1.0]]})

    embedder, calls = make_embedder(handler)

    result = await embedder.embed([])

    assert result == []
    assert calls == []


async def test_embed_returns_one_vector_per_text_in_positional_order(make_embedder) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"embeddings": [[1.0], [2.0], [3.0]]})

    embedder, _ = make_embedder(handler)

    result = await embedder.embed(["a", "b", "c"])

    assert result == [[1.0], [2.0], [3.0]]


async def test_embed_sends_all_texts_in_a_single_request(make_embedder) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"embeddings": [[1.0], [2.0], [3.0]]})

    embedder, calls = make_embedder(handler)

    await embedder.embed(["a", "b", "c"])

    assert len(calls) == 1
    assert json.loads(calls[0].content)["input"] == ["a", "b", "c"]


async def test_embed_returns_one_vector_for_a_single_element_batch(make_embedder) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"embeddings": [[1.0]]})

    embedder, calls = make_embedder(handler)

    result = await embedder.embed(["only text"])

    assert result == [[1.0]]
    assert len(calls) == 1


# --- response validation -------------------------------------------------


@pytest.mark.parametrize("body", [{"model": "m"}, {"embeddings": []}])
async def test_embed_raises_rather_than_returns_empty_list_when_embeddings_missing_or_empty(
    make_embedder, body: dict
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    embedder, _ = make_embedder(handler)

    with pytest.raises(ValueError, match="embeddings"):
        await embedder.embed(["a"])


async def test_embed_raises_naming_both_counts_when_fewer_vectors_returned_than_texts(make_embedder) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"embeddings": [[1.0]]})

    embedder, _ = make_embedder(handler)

    with pytest.raises(ValueError) as exc_info:
        await embedder.embed(["a", "b"])

    assert "1" in str(exc_info.value)
    assert "2" in str(exc_info.value)


async def test_embed_raises_when_more_vectors_returned_than_texts(make_embedder) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"embeddings": [[1.0], [2.0]]})

    embedder, _ = make_embedder(handler)

    with pytest.raises(ValueError):
        await embedder.embed(["a"])


async def test_embed_raises_when_any_returned_vector_is_empty(make_embedder) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"embeddings": [[0.1, 0.2], []]})

    embedder, _ = make_embedder(handler)

    with pytest.raises(ValueError):
        await embedder.embed(["a", "b"])


async def test_embed_raises_naming_conflicting_dimensions_when_vectors_have_inconsistent_lengths(
    make_embedder,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"embeddings": [[0.1, 0.2], [0.3]]})

    embedder, _ = make_embedder(handler)

    with pytest.raises(ValueError) as exc_info:
        await embedder.embed(["a", "b"])

    # the impl formats a `set`, so element ordering in the message is not stable
    assert "1" in str(exc_info.value)
    assert "2" in str(exc_info.value)


async def test_embed_accepts_a_batch_where_all_vectors_share_one_dimension(make_embedder) -> None:
    # negative control: a `len(dimensions) >= 1`-style mistake would pass every
    # failure case above and reject all valid input, so this must stay green.
    #
    # This dimension-consistency check is deliberately scoped to a single
    # `embed` call only: it does not check returned vectors against the
    # model's expected dimension, nor against any prior call's vectors — that
    # half is enforced loudly at the pgvector column on insert.
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"embeddings": [[0.1, 0.2], [0.3, 0.4]]})

    embedder, _ = make_embedder(handler)

    result = await embedder.embed(["a", "b"])

    assert result == [[0.1, 0.2], [0.3, 0.4]]


# --- request composition and transport -----------------------------------


async def test_embed_posts_the_wire_contract(make_embedder) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"embeddings": [[1.0], [2.0]]})

    embedder, calls = make_embedder(handler)

    await embedder.embed(["one", "two"])

    request = calls[0]
    assert request.url == f"{BASE_URL}/api/embed"
    assert json.loads(request.content) == {
        "model": MODEL,
        "input": ["one", "two"],
    }


async def test_embed_attaches_bearer_header_when_api_key_is_set(make_embedder) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"embeddings": [[1.0]]})

    embedder, calls = make_embedder(handler, api_key="secret-key")

    await embedder.embed(["a"])

    assert calls[0].headers["Authorization"] == "Bearer secret-key"


@pytest.mark.parametrize("api_key", [None, ""])
async def test_embed_omits_bearer_header_when_no_api_key(make_embedder, api_key: str | None) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"embeddings": [[1.0]]})

    embedder, calls = make_embedder(handler, api_key=api_key)

    await embedder.embed(["a"])

    assert "Authorization" not in calls[0].headers


async def test_embed_propagates_a_read_timeout(make_embedder) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    embedder, _ = make_embedder(handler)

    with pytest.raises(httpx.ReadTimeout):
        await embedder.embed(["a"])


async def test_embed_propagates_a_non_2xx_response(make_embedder) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    embedder, _ = make_embedder(handler)

    with pytest.raises(httpx.HTTPStatusError):
        await embedder.embed(["a"])


async def test_embed_client_carries_the_configured_timeout(make_embedder) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"embeddings": [[1.0]]})

    embedder, _ = make_embedder(handler, timeout=5.0)

    assert embedder._timeout == 5.0


async def test_embed_client_defaults_to_120_second_timeout(make_embedder) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"embeddings": [[1.0]]})

    embedder, _ = make_embedder(handler)

    assert embedder._timeout == 120.0


# --- boundary ABC conformance ---------------------------------------------


def test_ollama_client_and_embedder_are_instances_of_their_model_agnostic_abcs() -> None:
    client = OllamaClient(BASE_URL, MODEL)
    embedder = OllamaEmbedder(BASE_URL, MODEL)

    assert isinstance(client, LLMClient)
    assert isinstance(embedder, Embedder)


def test_abc_boundary_is_free_of_any_ollama_concept() -> None:
    # Both src/llm/client.py and src/llm/embedder.py contain "Ollama" outside
    # the ABC (the concrete class name and the error strings), so scanning
    # the whole module file would fail red for the wrong reason.
    # `inspect.getsource(cls)` returns only the ABC class body and is the
    # correct, unambiguous scope for this guard.
    assert "ollama" not in inspect.getsource(LLMClient).lower()
    assert "ollama" not in inspect.getsource(Embedder).lower()
