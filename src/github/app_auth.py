import threading
import time
from dataclasses import dataclass

import httpx
import jwt

# Installation tokens live ~1 hour server-side; cache validity trims a safety
# margin off that so a caller never hands out a token that expires mid-use.
_VALID_FOR_SECONDS = 3600 - 300

_API_BASE_URL = "https://api.github.com"


@dataclass(frozen=True)
class _CacheEntry:
    token: str
    expires_at: float


class GitHubAppAuth:
    """Mints per-org GitHub App installation tokens: App JWT to installation
    token, single-flight per org, cached until shortly before expiry."""

    def __init__(self, app_id: int, private_key: str) -> None:
        self._app_id = app_id
        self._private_key = private_key
        self._cache: dict[int, _CacheEntry] = {}
        self._org_locks: dict[int, threading.Lock] = {}
        self._org_locks_guard = threading.Lock()

    def token(self, org_id: int) -> str:
        entry = self._cache.get(org_id)
        if entry is not None and time.monotonic() < entry.expires_at:
            return entry.token

        lock = self._org_lock(org_id)
        with lock:
            entry = self._cache.get(org_id)
            if entry is not None and time.monotonic() < entry.expires_at:
                return entry.token

            fresh_token = self._mint_token(org_id)
            self._cache[org_id] = _CacheEntry(
                token=fresh_token,
                expires_at=time.monotonic() + _VALID_FOR_SECONDS,
            )
            return fresh_token

    def _org_lock(self, org_id: int) -> threading.Lock:
        lock = self._org_locks.get(org_id)
        if lock is not None:
            return lock
        with self._org_locks_guard:
            lock = self._org_locks.setdefault(org_id, threading.Lock())
        return lock

    def _mint_token(self, org_id: int, api_base_url: str = _API_BASE_URL) -> str:
        now = int(time.time())
        app_jwt = jwt.encode(
            {"iat": now - 60, "exp": now + 540, "iss": self._app_id},
            self._private_key,
            algorithm="RS256",
        )
        headers = {
            "Authorization": f"Bearer {app_jwt}",
            "Accept": "application/vnd.github+json",
        }

        with httpx.Client(base_url=api_base_url, headers=headers) as client:
            installation_id = self._resolve_installation_id(client, org_id)
            response = client.post(f"/app/installations/{installation_id}/access_tokens")
            response.raise_for_status()
            return response.json()["token"]

    def _resolve_installation_id(self, client: httpx.Client, org_id: int) -> int:
        url = "/app/installations"
        params: dict[str, str] | None = {"per_page": "100"}
        while url is not None:
            response = client.get(url, params=params)
            response.raise_for_status()
            for installation in response.json():
                account = installation["account"]
                if account["id"] == org_id and account["type"] == "Organization":
                    return installation["id"]

            url = response.links.get("next", {}).get("url")
            params = None

        raise LookupError(f"No GitHub App installation found for organization {org_id}")
