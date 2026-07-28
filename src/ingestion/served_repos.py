from collections.abc import Iterable

import asyncpg


class ServedRepoStore:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def add(self, org_id: int, repos: Iterable[str]) -> None:
        rows = [(org_id, repo) for repo in repos]
        if not rows:
            return
        async with self._pool.acquire() as conn:
            await conn.executemany(
                "INSERT INTO served_repos (org_id, repo) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                rows,
            )

    async def remove(self, org_id: int, repos: Iterable[str]) -> None:
        repos = list(repos)
        if not repos:
            return
        async with self._pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM served_repos WHERE org_id = $1 AND repo = ANY($2::text[])",
                org_id,
                repos,
            )

    async def all(self) -> list[tuple[int, str]]:
        """Return every `(org_id, repo)` pair currently served, ordered for
        stable, idempotent iteration. This is the authoritative served set —
        callers iterate this rather than guessing `org_id` from a mirror
        directory listing."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("SELECT org_id, repo FROM served_repos ORDER BY org_id, repo")
        return [(row["org_id"], row["repo"]) for row in rows]
