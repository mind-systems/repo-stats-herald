import hashlib
import hmac
import json
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from src.core.config import get_settings
from src.main import app

TEST_WEBHOOK_SECRET = "test-webhook-secret"

TEST_ORG_ID = 244165546
TEST_ORG_LOGIN = "mind-systems"


@pytest.fixture
def webhook_secret_env(monkeypatch: pytest.MonkeyPatch) -> str:
    """Set GITHUB_WEBHOOK_SECRET and clear get_settings' cache so 2.1.2's
    Settings-backed verification reads the same secret the tests sign with."""
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)
    monkeypatch.setenv("SERVE_ALLOWLIST", str(TEST_ORG_ID))
    get_settings.cache_clear()
    yield TEST_WEBHOOK_SECRET
    get_settings.cache_clear()


@pytest.fixture
def client(webhook_secret_env: str) -> TestClient:
    return TestClient(app)


@pytest.fixture
def sign() -> Callable[[bytes], str]:
    def _sign(body: bytes, secret: str = TEST_WEBHOOK_SECRET) -> str:
        digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        return f"sha256={digest}"

    return _sign


@pytest.fixture
def push_payload() -> Callable[..., bytes]:
    def _push_payload(*, ref: str = "refs/heads/main") -> bytes:
        payload = {
            "ref": ref,
            "before": "0" * 40,
            "after": "1" * 40,
            "repository": {"name": "repo-stats-herald"},
            "organization": {"id": TEST_ORG_ID, "login": TEST_ORG_LOGIN},
            "commits": [
                {
                    "id": "abc123def456",
                    "message": "Add feature",
                    "added": ["src/new_file.py"],
                    "modified": ["src/main.py"],
                    "removed": [],
                    "author": {"name": "Jane Dev"},
                }
            ],
        }
        return json.dumps(payload).encode()

    return _push_payload
