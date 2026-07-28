import httpx
import pytest

from src.delivery.changelog_client import ChangelogClient, ChangelogEntry

BASE_URL = "https://app.example.com"


class FakeResponse:
    """Stub `httpx.Response` — `raise_for_status` no-ops unless configured
    with an error to raise, simulating a non-2xx or transport failure.
    `json()` returns whatever body the stub server was configured with."""

    def __init__(self, body: object = None, error: Exception | None = None) -> None:
        self._body = body
        self._error = error

    def raise_for_status(self) -> None:
        if self._error is not None:
            raise self._error

    def json(self) -> object:
        return self._body


class FakeAsyncClient:
    """Fake stand-in for `httpx.AsyncClient` as an async context manager,
    playing the role of a stub server implementing the two changelog
    endpoints. Routes on method + URL suffix: `GET .../config` returns the
    stub's declared `languages`; `POST .../entry` records the posted body
    and returns `201`."""

    def __init__(
        self,
        posted: list[tuple[str, dict]],
        languages: list[str],
        error: Exception | None,
    ) -> None:
        self._posted = posted
        self._languages = languages
        self._error = error

    async def __aenter__(self) -> "FakeAsyncClient":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def get(self, url: str) -> FakeResponse:
        assert url == f"{BASE_URL}/internal/changelog/config"
        return FakeResponse(body={"languages": self._languages}, error=self._error)

    async def post(self, url: str, json: dict) -> FakeResponse:
        assert url == f"{BASE_URL}/internal/changelog/entry"
        self._posted.append((url, json))
        return FakeResponse(error=self._error)


def _install_fake_transport(
    monkeypatch: pytest.MonkeyPatch,
    languages: list[str] | None = None,
    error: Exception | None = None,
) -> list[tuple[str, dict]]:
    posted: list[tuple[str, dict]] = []

    def factory(*args: object, **kwargs: object) -> FakeAsyncClient:
        return FakeAsyncClient(posted, languages or [], error)

    monkeypatch.setattr("src.delivery.changelog_client.httpx.AsyncClient", factory)
    return posted


async def test_config_returns_the_stubs_declared_languages(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_transport(monkeypatch, languages=["ru", "en"])
    client = ChangelogClient()

    languages = await client.config(BASE_URL)

    assert languages == ["ru", "en"]


async def test_entry_posts_a_well_formed_body(monkeypatch: pytest.MonkeyPatch) -> None:
    posted = _install_fake_transport(monkeypatch, languages=["ru", "en"])
    client = ChangelogClient()
    payload = ChangelogEntry(
        version="v1.2.0",
        environment="production",
        summaries={"ru": "русский текст", "en": "english text"},
        github_url="https://github.com/org/repo/releases/tag/v1.2.0",
    )

    await client.entry(BASE_URL, payload)

    assert len(posted) == 1
    url, body = posted[0]
    assert url == f"{BASE_URL}/internal/changelog/entry"
    assert set(body.keys()) == {"version", "environment", "summaries", "github_url"}
    assert body["version"] == "v1.2.0"
    assert body["environment"] in ("staging", "production")
    assert body["summaries"] == {"ru": "русский текст", "en": "english text"}
    assert body["github_url"] == "https://github.com/org/repo/releases/tag/v1.2.0"


@pytest.mark.parametrize("languages", [["en"], ["ru", "en"], ["ru", "en", "es"]])
async def test_entry_summaries_key_set_matches_exactly_the_declared_language_count(
    monkeypatch: pytest.MonkeyPatch, languages: list[str]
) -> None:
    posted = _install_fake_transport(monkeypatch, languages=languages)
    client = ChangelogClient()
    declared = await client.config(BASE_URL)
    payload = ChangelogEntry(
        version="v1.0.0",
        environment="staging",
        summaries={lang: f"summary in {lang}" for lang in declared},
        github_url="https://github.com/org/repo/releases/tag/v1.0.0",
    )

    await client.entry(BASE_URL, payload)

    _, body = posted[0]
    assert set(body["summaries"].keys()) == set(languages)


async def test_config_transport_error_raises_and_is_not_swallowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    error = httpx.HTTPStatusError("Not Found", request=None, response=None)
    _install_fake_transport(monkeypatch, error=error)
    client = ChangelogClient()

    with pytest.raises(httpx.HTTPStatusError):
        await client.config(BASE_URL)


async def test_entry_non_2xx_response_raises_and_is_not_swallowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    error = httpx.HTTPStatusError("Bad Request", request=None, response=None)
    _install_fake_transport(monkeypatch, error=error)
    client = ChangelogClient()
    payload = ChangelogEntry(
        version="v1.0.0",
        environment="staging",
        summaries={"en": "text"},
        github_url="https://github.com/org/repo/releases/tag/v1.0.0",
    )

    with pytest.raises(httpx.HTTPStatusError):
        await client.entry(BASE_URL, payload)
