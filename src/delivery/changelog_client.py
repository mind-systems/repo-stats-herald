from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class ChangelogEntry:
    """One changelog entry for a released version, 1:1 with the frozen
    `{version, environment, summaries, github_url}` wire shape. `summaries`
    is an open `dict[str, str]` — no language is fixed here."""

    version: str
    environment: str
    summaries: dict[str, str]
    github_url: str


class ChangelogClient:
    """Speaks the two-endpoint internal changelog protocol toward an
    integrated app. Holds no config of its own — the base URL is plan-state,
    resolved per push and passed in on every call. No API key: the internal
    network is the trust boundary."""

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    async def config(self, base_url: str) -> list[str]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(f"{base_url}/internal/changelog/config")
            response.raise_for_status()
            return response.json()["languages"]

    async def entry(self, base_url: str, payload: ChangelogEntry) -> None:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                f"{base_url}/internal/changelog/entry",
                json={
                    "version": payload.version,
                    "environment": payload.environment,
                    "summaries": payload.summaries,
                    "github_url": payload.github_url,
                },
            )
            response.raise_for_status()
