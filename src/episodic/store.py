from abc import ABC, abstractmethod
from datetime import datetime

import asyncpg

from src.episodic.models import EpisodicEntry


class EpisodicStore(ABC):
    @abstractmethod
    async def append(self, entry: EpisodicEntry) -> None:
        """Append one entry. The log is append-only — entries are never
        mutated or removed."""
        ...

    @abstractmethod
    async def query(
        self,
        embedding: list[float],
        k: int,
        repo: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[EpisodicEntry]:
        """Return up to `k` entries ordered nearest-first by cosine distance
        to `embedding`, optionally scoped to `repo`. `since`/`until` bound
        the window on `changed_at` (the commit timestamp — the historical
        key), never on `recorded_at`."""
        ...

    @abstractmethod
    async def recorded_commit_shas(self, repo: str) -> set[str]:
        """Return the union of every `commit_shas` element already stored
        for `repo`, across all entries. Used to skip commits already covered
        by a prior backfill run or a live push."""
        ...


class PgEpisodicStore(EpisodicStore):
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def append(self, entry: EpisodicEntry) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO episodic_entries
                    (repo, org_id, completed_tasks, commit_shas, content, embedding, changed_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                entry.repo,
                entry.org_id,
                list(entry.completed_tasks),
                list(entry.commit_shas),
                entry.content,
                entry.embedding,
                entry.changed_at,
            )

    async def query(
        self,
        embedding: list[float],
        k: int,
        repo: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[EpisodicEntry]:
        clauses = []
        params: list[object] = []

        if repo is not None:
            params.append(repo)
            clauses.append(f"repo = ${len(params)}")
        if since is not None:
            params.append(since)
            clauses.append(f"changed_at >= ${len(params)}")
        if until is not None:
            params.append(until)
            clauses.append(f"changed_at <= ${len(params)}")

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

        params.append(embedding)
        order_param = len(params)
        params.append(k)
        limit_param = len(params)

        sql = f"""
            SELECT repo, org_id, completed_tasks, commit_shas, content, embedding, changed_at, recorded_at
            FROM episodic_entries
            {where}
            ORDER BY embedding <=> ${order_param}
            LIMIT ${limit_param}
            """

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)

        return [
            EpisodicEntry(
                repo=row["repo"],
                org_id=row["org_id"],
                completed_tasks=tuple(row["completed_tasks"]),
                commit_shas=tuple(row["commit_shas"]),
                content=row["content"],
                embedding=row["embedding"],
                changed_at=row["changed_at"],
                recorded_at=row["recorded_at"],
            )
            for row in rows
        ]

    async def recorded_commit_shas(self, repo: str) -> set[str]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT DISTINCT unnest(commit_shas) AS sha FROM episodic_entries WHERE repo = $1",
                repo,
            )
        return {row["sha"] for row in rows}
