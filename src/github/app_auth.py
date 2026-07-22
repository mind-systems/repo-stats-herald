class GitHubAppAuth:
    """Mints per-org GitHub App installation tokens: App JWT to installation
    token, single-flight per org, cached until shortly before expiry."""

    def __init__(self, app_id: int, private_key: str) -> None:
        self._app_id = app_id
        self._private_key = private_key

    def token(self, org_id: int) -> str:
        raise NotImplementedError

    def _mint_token(self, org_id: int) -> str:
        raise NotImplementedError
