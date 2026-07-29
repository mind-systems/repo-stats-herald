import httpx
import pytest

from src.delivery.telegram import TelegramClient, TelegramSendError

TOKEN = "test-token"


class FakeResponse:
    """Stub `httpx.Response` — `raise_for_status` no-ops unless configured
    with an error to raise, simulating a non-2xx or transport failure."""

    def __init__(self, error: Exception | None = None) -> None:
        self._error = error

    def raise_for_status(self) -> None:
        if self._error is not None:
            raise self._error


class FakeAsyncClient:
    """Fake stand-in for `httpx.AsyncClient` as an async context manager.
    Records every `post(url, json=...)` call into the shared `calls` list
    and returns a `FakeResponse` configured with the shared `error`."""

    def __init__(self, calls: list[tuple[str, dict]], error: Exception | None) -> None:
        self._calls = calls
        self._error = error

    async def __aenter__(self) -> "FakeAsyncClient":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def post(self, url: str, json: dict) -> FakeResponse:
        self._calls.append((url, json))
        return FakeResponse(self._error)


def _install_fake_transport(
    monkeypatch: pytest.MonkeyPatch, error: Exception | None = None
) -> list[tuple[str, dict]]:
    calls: list[tuple[str, dict]] = []

    def factory(*args: object, **kwargs: object) -> FakeAsyncClient:
        return FakeAsyncClient(calls, error)

    monkeypatch.setattr("src.delivery.telegram.httpx.AsyncClient", factory)
    return calls


async def test_single_short_message_posts_exactly_once(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _install_fake_transport(monkeypatch)
    client = TelegramClient(TOKEN)

    await client.send("chat", "hello")

    assert len(calls) == 1
    url, body = calls[0]
    assert url.endswith(f"/bot{TOKEN}/sendMessage")
    assert body["chat_id"] == "chat"
    assert body["text"] == "hello"
    assert "parse_mode" not in body


async def test_over_length_message_splits_into_ordered_lossless_parts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _install_fake_transport(monkeypatch)
    client = TelegramClient(TOKEN)
    text = "".join(str(i % 10) for i in range(4096 * 2 + 123))

    await client.send("chat", text)

    parts = [body["text"] for _, body in calls]
    assert all(len(part) <= 4096 for part in parts)
    assert len(parts) >= 3
    assert "".join(parts) == text


async def test_astral_dense_message_splits_by_utf16_length(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _install_fake_transport(monkeypatch)
    client = TelegramClient(TOKEN)
    text = "😀" * 2049  # each code point costs 2 UTF-16 units: len(text) <= 4096, UTF-16 length > 4096

    await client.send("chat", text)

    parts = [body["text"] for _, body in calls]
    assert len(parts) >= 2
    assert all(len(part.encode("utf-16-le")) // 2 <= 4096 for part in parts)
    assert "".join(parts) == text


def _assert_no_token_reachable(exc: TelegramSendError) -> None:
    assert TOKEN not in str(exc)
    assert TOKEN not in repr(exc)
    for value in vars(exc).values():
        assert TOKEN not in str(value)
        assert TOKEN not in repr(value)
    assert exc.__cause__ is None
    assert exc.__context__ is None


async def test_bad_token_response_raises_and_is_not_swallowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = httpx.Request("POST", f"https://api.telegram.org/bot{TOKEN}/sendMessage")
    response = httpx.Response(400, request=request)
    error = httpx.HTTPStatusError("Bad Request", request=request, response=response)
    _install_fake_transport(monkeypatch, error=error)
    client = TelegramClient(TOKEN)

    with pytest.raises(TelegramSendError) as exc_info:
        await client.send("chat", "hello")

    exc = exc_info.value
    assert exc.status_code == 400
    _assert_no_token_reachable(exc)


async def test_transport_failure_raises_and_is_not_swallowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = httpx.Request("POST", f"https://api.telegram.org/bot{TOKEN}/sendMessage")
    error = httpx.ConnectError("Connection failed", request=request)
    _install_fake_transport(monkeypatch, error=error)
    client = TelegramClient(TOKEN)

    with pytest.raises(TelegramSendError) as exc_info:
        await client.send("chat", "hello")

    exc = exc_info.value
    assert exc.status_code is None
    _assert_no_token_reachable(exc)
