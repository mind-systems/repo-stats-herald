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
