import httpx

from src.github.app_auth import GitHubAppAuth
from src.versioning.versioner import Version

_API_BASE_URL = "https://api.github.com"


class GitHubReleaseClient:
    """Cuts a GitHub release for a served repo — the App-authenticated
    transport only, never deciding the version or the note text itself."""

    def __init__(self, auth: GitHubAppAuth) -> None:
        self._auth = auth

    async def create(
        self,
        org_id: int,
        owner: str,
        repo: str,
        version: Version,
        body: str,
        prerelease: bool,
        target_commitish: str,
    ) -> str:
        token = self._auth.token(org_id)
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        tag_name = str(version)
        async with httpx.AsyncClient(base_url=_API_BASE_URL, headers=headers) as client:
            response = await client.post(
                f"/repos/{owner}/{repo}/releases",
                json={
                    "tag_name": tag_name,
                    "name": tag_name,
                    "target_commitish": target_commitish,
                    "body": body,
                    "prerelease": prerelease,
                },
            )
            response.raise_for_status()
            return response.json()["html_url"]
