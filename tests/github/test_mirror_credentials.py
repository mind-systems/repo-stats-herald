"""Pins `RepoMirror`'s credential handling: on an http(s) clone source the
installation token travels through the process environment
(`GIT_CONFIG_*`) and must stay out of the argument list, out of the
persisted `origin` remote, and out of the text and attributes of a raised
failure. A non-http(s) source (the plain filesystem path the other mirror
suites clone from) never mints a token at all.

Lifecycle, refs and on-disk worktree state are covered in
`test_mirror_lifecycle.py`; concurrency in `test_mirror_isolation.py`. This
module is the credential group only.
"""

import base64
import subprocess

import pytest

from src.github.mirror import RepoMirror

REPO = "example-repo"
ORG_ID = 1
_TOKEN = "ghs_SECRET"


def _basic_value(token: str) -> str:
    basic = base64.b64encode(f"x-access-token:{token}".encode()).decode()
    return f"Authorization: Basic {basic}"


# --- Phase 1: persisted-remote safety — real run against `local_upstream` --


def test_ensure_keeps_persisted_remote_url_equal_to_the_plain_upstream_path(
    mirror, local_upstream
):
    mirror.ensure(REPO, ORG_ID)

    bare_path = mirror.object_store_path(REPO)
    result = subprocess.run(
        ["git", "-C", str(bare_path), "config", "--get", "remote.origin.url"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == str(local_upstream.path)


def test_ensure_writes_no_authorization_or_token_string_into_bare_store_config(
    mirror, local_upstream
):
    mirror.ensure(REPO, ORG_ID)

    bare_path = mirror.object_store_path(REPO)
    config_text = (bare_path / "config").read_text()
    assert "Authorization" not in config_text
    assert "x-access-token" not in config_text


# --- Phase 2: token travels through the environment, not argv -------------


class _RecordingRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[tuple, dict]] = []

    def __call__(self, *args, **kwargs) -> subprocess.CompletedProcess:
        self.calls.append((args, kwargs))
        return subprocess.CompletedProcess(args[0] if args else [], returncode=0, stdout="")


def test_https_clone_passes_token_only_via_git_config_env(tmp_path, auth, monkeypatch):
    monkeypatch.setattr(auth, "token", lambda org_id: _TOKEN)
    runner = _RecordingRunner()
    local_mirror = RepoMirror(
        mirror_root=tmp_path / "mirror",
        auth=auth,
        clone_source=lambda repo, org_id: "https://github.com/acme/example-repo.git",
        run=runner,
    )

    local_mirror.ensure(REPO, ORG_ID)

    clone_args, clone_kwargs = next(
        call for call in runner.calls if call[0][0][1] == "clone"
    )
    argv = clone_args[0]

    assert all(_TOKEN not in element for element in argv)

    source_arg = next(a for a in argv if a.startswith("https://"))
    assert "@" not in source_arg

    env = clone_kwargs["env"]
    assert env["GIT_CONFIG_COUNT"] == "1"
    assert env["GIT_CONFIG_KEY_0"] == "http.extraHeader"
    assert env["GIT_CONFIG_VALUE_0"] == _basic_value(_TOKEN)


def test_fetch_path_carries_the_same_credential_as_clone(tmp_path, auth, monkeypatch):
    monkeypatch.setattr(auth, "token", lambda org_id: _TOKEN)
    runner = _RecordingRunner()
    local_mirror = RepoMirror(
        mirror_root=tmp_path / "mirror",
        auth=auth,
        clone_source=lambda repo, org_id: "https://github.com/acme/example-repo.git",
        run=runner,
    )
    local_mirror.object_store_path(REPO).mkdir(parents=True)

    local_mirror.ensure(REPO, ORG_ID)

    fetch_args, fetch_kwargs = next(
        call for call in runner.calls if call[0][0][1] == "fetch"
    )
    argv = fetch_args[0]

    assert all(_TOKEN not in element for element in argv)

    env = fetch_kwargs["env"]
    assert env["GIT_CONFIG_COUNT"] == "1"
    assert env["GIT_CONFIG_KEY_0"] == "http.extraHeader"
    assert env["GIT_CONFIG_VALUE_0"] == _basic_value(_TOKEN)


# --- Phase 3: no token minted for non-http(s) sources ----------------------


def test_ensure_never_consults_auth_token_for_a_filesystem_source(
    mirror, local_upstream, monkeypatch, auth
):
    def _raise(org_id):
        raise AssertionError("auth.token must not be consulted for a filesystem source")

    monkeypatch.setattr(auth, "token", _raise)

    mirror.ensure(REPO, ORG_ID)


@pytest.mark.parametrize(
    ("source", "expect_token"),
    [
        pytest.param("local_upstream_path", False, id="plain filesystem path"),
        pytest.param("file:///tmp/example-repo.git", False, id="file scheme"),
        pytest.param("ssh://git@github.com/acme/example-repo.git", False, id="ssh scheme"),
        pytest.param("git@github.com:acme/example-repo.git", False, id="scp-style"),
        pytest.param("http://github.com/acme/example-repo.git", True, id="http scheme"),
        pytest.param("https://github.com/acme/example-repo.git", True, id="https scheme"),
    ],
)
def test_credential_for_mints_a_token_only_for_http_schemes(
    mirror, local_upstream, auth, monkeypatch, source, expect_token
):
    monkeypatch.setattr(auth, "token", lambda org_id: _TOKEN)
    if source == "local_upstream_path":
        source = str(local_upstream.path)

    result = mirror._credential_for(source, ORG_ID)

    assert result == (_TOKEN if expect_token else None)


# --- Phase 4: token absent from the raised failure -------------------------


def test_failing_credentialed_clone_raises_called_process_error_without_leaking_token(
    tmp_path, auth, monkeypatch
):
    monkeypatch.setattr(auth, "token", lambda org_id: _TOKEN)
    local_mirror = RepoMirror(
        mirror_root=tmp_path / "mirror",
        auth=auth,
        clone_source=lambda repo, org_id: "https://127.0.0.1:1/x.git",
    )

    with pytest.raises(subprocess.CalledProcessError) as exc_info:
        local_mirror.ensure(REPO, ORG_ID)

    exc = exc_info.value
    assert _TOKEN not in str(exc)
    assert _TOKEN not in " ".join(exc.cmd)
    assert _TOKEN.encode() not in (exc.stdout or b"")
    assert _TOKEN.encode() not in (exc.stderr or b"")
