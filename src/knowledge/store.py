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
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def upsert(self, repo: str, path: str, items: list[Chunk]) -> None:
        raise NotImplementedError

    async def delete(self, repo: str, path: str) -> None:
        raise NotImplementedError

    async def query(self, embedding: list[float], k: int, repo: str | None = None) -> list[Chunk]:
        raise NotImplementedError
