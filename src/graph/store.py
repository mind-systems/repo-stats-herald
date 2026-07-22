from abc import ABC, abstractmethod

import asyncpg

from src.graph.models import Edge


class ProjectGraph(ABC):
    @abstractmethod
    async def add_edge(self, edge: Edge) -> None:
        """Persist `edge`. A `source='seed'` write that collides with an
        existing edge on the same `(from_repo, to_repo, kind)` triple must
        NOT downgrade a stored `config` edge's `source`, and re-adding an
        identical `config` edge is idempotent (no duplicate, no error)."""
        ...

    @abstractmethod
    async def edges_from(self, repo: str) -> list[Edge]:
        """Return every stored edge whose `from_repo == repo`, hydrated with
        its stored `source`."""
        ...

    @abstractmethod
    async def neighbors(self, repo: str) -> list[str]:
        """Return the `to_repo` of every edge `repo -> ...`; directed, never
        symmetric."""
        ...

    @abstractmethod
    async def remove_seed_edges(self, from_repo: str) -> None:
        """Delete only rows with `source='seed'` for that `from_repo`;
        `config` rows untouched."""
        ...


class PgProjectGraph(ProjectGraph):
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def add_edge(self, edge: Edge) -> None:
        raise NotImplementedError

    async def edges_from(self, repo: str) -> list[Edge]:
        raise NotImplementedError

    async def neighbors(self, repo: str) -> list[str]:
        raise NotImplementedError

    async def remove_seed_edges(self, from_repo: str) -> None:
        raise NotImplementedError
