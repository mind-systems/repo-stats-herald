import json

import httpx
import pytest

from tests.llm.conftest import BASE_URL, MODEL

# --- response parsing -------------------------------------------------


async def test_generate_raises_rather_than_returns_empty_string(make_client) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"response": ""})

    client, _ = make_client(handler)

    with pytest.raises(ValueError, match="Ollama"):
        await client.generate("prompt")


async def test_generate_raises_rather_than_returns_whitespace_only_string(make_client) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"response": "   \n  "})

    client, _ = make_client(handler)

    with pytest.raises(ValueError, match="Ollama"):
        await client.generate("prompt")


async def test_generate_raises_a_typed_error_when_response_key_is_missing(make_client) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"model": "qwen2.5", "done": True})

    client, _ = make_client(handler)

    with pytest.raises(ValueError, match="response"):
        await client.generate("prompt")


@pytest.mark.parametrize("body", [None, "some string"])
async def test_generate_raises_when_body_is_not_a_json_object(make_client, body: object) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=json.dumps(body))

    client, _ = make_client(handler)

    with pytest.raises(ValueError, match="Ollama"):
        await client.generate("prompt")


async def test_generate_returns_real_text_exactly_as_received(make_client) -> None:
    text = "  leading and trailing whitespace around real content  "

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"response": text})

    client, _ = make_client(handler)

    result = await client.generate("prompt")

    assert result == text


# --- transport ----------------------------------------------------------


async def test_generate_propagates_a_read_timeout(make_client) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    client, _ = make_client(handler)

    with pytest.raises(httpx.ReadTimeout):
        await client.generate("prompt")


async def test_generate_propagates_a_non_2xx_response(make_client) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    client, _ = make_client(handler)

    with pytest.raises(httpx.HTTPStatusError):
        await client.generate("prompt")


async def test_generate_propagates_a_connect_error(make_client) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection failed", request=request)

    client, _ = make_client(handler)

    with pytest.raises(httpx.ConnectError):
        await client.generate("prompt")


# --- request composition -------------------------------------------------


async def test_generate_attaches_bearer_header_when_api_key_is_set(make_client) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"response": "text"})

    client, calls = make_client(handler, api_key="secret-key")

    await client.generate("prompt")

    assert calls[0].headers["Authorization"] == "Bearer secret-key"


@pytest.mark.parametrize("api_key", [None, ""])
async def test_generate_omits_bearer_header_when_no_api_key(make_client, api_key: str | None) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"response": "text"})

    client, calls = make_client(handler, api_key=api_key)

    await client.generate("prompt")

    assert "Authorization" not in calls[0].headers


async def test_generate_posts_the_wire_contract(make_client) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"response": "text"})

    client, calls = make_client(handler)

    await client.generate("the prompt text")

    request = calls[0]
    assert request.url == f"{BASE_URL}/api/generate"
    assert json.loads(request.content) == {
        "model": MODEL,
        "prompt": "the prompt text",
        "stream": False,
    }


# --- timeout plumbing -------------------------------------------------


async def test_generate_client_carries_the_configured_timeout(make_client) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"response": "text"})

    client, _ = make_client(handler, timeout=5.0)

    assert client._timeout == 5.0


async def test_generate_client_defaults_to_120_second_timeout(make_client) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"response": "text"})

    client, _ = make_client(handler)

    assert client._timeout == 120.0
