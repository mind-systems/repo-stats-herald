from abc import ABC, abstractmethod
from dataclasses import dataclass

import asyncpg


@dataclass(frozen=True)
class Chunk:
    content: str
    embedding: list[float]
    repo: str | None = None
    path: str | None = None
    chunk_index: int | None = None


class KnowledgeStore(ABC):
    @abstractmethod
    async def upsert(self, repo: str, path: str, items: list[Chunk]) -> None:
        """Replace all chunks for `(repo, path)` with `items`, atomically.

        The write must be all-or-nothing: a caller never observes a mix of
        old and new chunks for the same `(repo, path)`, and no chunk from a
        previous upsert of the same `(repo, path)` survives past index
        `len(items) - 1`.
        """
        ...

    @abstractmethod
    async def delete(self, repo: str, path: str) -> None:
        """Remove all chunks for `(repo, path)` only — every other path and
        repo is left untouched."""
        ...

    @abstractmethod
    async def query(self, embedding: list[float], k: int, repo: str | None = None) -> list[Chunk]:
        """Return up to `k` chunks ordered nearest-first by cosine distance
        to `embedding`, optionally scoped to `repo`. Each returned `Chunk`
        is hydrated with the `repo`, `path`, and `chunk_index` it was stored
        under, so callers can identify a chunk's source."""
        ...


class PgVectorStore(KnowledgeStore):
    _DELETE_SQL = "DELETE FROM chunks WHERE repo = $1 AND path = $2"

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def upsert(self, repo: str, path: str, items: list[Chunk]) -> None:
        rows = [
            (repo, path, index, item.content, item.embedding)
            for index, item in enumerate(items)
        ]
        async with self._pool.acquire() as conn, conn.transaction():
            await conn.execute(self._DELETE_SQL, repo, path)
            if rows:
                await conn.executemany(
                    """
                    INSERT INTO chunks (repo, path, chunk_index, content, embedding)
                    VALUES ($1, $2, $3, $4, $5)
                    """,
                    rows,
                )

    async def delete(self, repo: str, path: str) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(self._DELETE_SQL, repo, path)

    async def query(self, embedding: list[float], k: int, repo: str | None = None) -> list[Chunk]:
        if repo is None:
            sql = """
                SELECT repo, path, chunk_index, content, embedding
                FROM chunks
                ORDER BY embedding <=> $1
                LIMIT $2
                """
            params = (embedding, k)
        else:
            sql = """
                SELECT repo, path, chunk_index, content, embedding
                FROM chunks
                WHERE repo = $1
                ORDER BY embedding <=> $2
                LIMIT $3
                """
            params = (repo, embedding, k)

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)

        return [
            Chunk(
                content=row["content"],
                embedding=row["embedding"],
                repo=row["repo"],
                path=row["path"],
                chunk_index=row["chunk_index"],
            )
            for row in rows
        ]
