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


class PgEpisodicStore(EpisodicStore):
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def append(self, entry: EpisodicEntry) -> None:
        raise NotImplementedError

    async def query(
        self,
        embedding: list[float],
        k: int,
        repo: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[EpisodicEntry]:
        raise NotImplementedError
