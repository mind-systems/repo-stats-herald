from abc import ABC, abstractmethod

import asyncpg

from src.graph.models import Edge, EdgeKind


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

    @abstractmethod
    async def replace_seed_edges(self, from_repo: str, edges: list[Edge]) -> None:
        """Atomically replace `from_repo`'s entire `source='seed'` set: delete
        its prior seed rows and insert `edges` in one transaction, so a
        re-seed never leaves a partial set. `config` rows are never touched.
        A seed edge colliding with an existing `config` edge on the same
        `(from_repo, to_repo, kind)` triple does nothing (the config edge
        wins). Concurrent replaces for the same `from_repo` serialize —
        never interleave into a partial/duplicated set."""
        ...


class PgProjectGraph(ProjectGraph):
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def add_edge(self, edge: Edge) -> None:
        if edge.source == "config":
            conflict_clause = "DO UPDATE SET source = EXCLUDED.source"
        else:
            conflict_clause = "DO NOTHING"

        async with self._pool.acquire() as conn:
            await conn.execute(
                f"""
                INSERT INTO project_edges (from_repo, to_repo, kind, source)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (from_repo, to_repo, kind) {conflict_clause}
                """,
                edge.from_repo,
                edge.to_repo,
                edge.kind.value,
                edge.source,
            )

    async def edges_from(self, repo: str) -> list[Edge]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT from_repo, to_repo, kind, source FROM project_edges WHERE from_repo = $1",
                repo,
            )
        return [
            Edge(
                from_repo=row["from_repo"],
                to_repo=row["to_repo"],
                kind=EdgeKind(row["kind"]),
                source=row["source"],
            )
            for row in rows
        ]

    async def neighbors(self, repo: str) -> list[str]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT to_repo FROM project_edges WHERE from_repo = $1 ORDER BY to_repo",
                repo,
            )
        return [row["to_repo"] for row in rows]

    async def remove_seed_edges(self, from_repo: str) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM project_edges WHERE from_repo = $1 AND source = 'seed'",
                from_repo,
            )

    async def replace_seed_edges(self, from_repo: str, edges: list[Edge]) -> None:
        async with self._pool.acquire() as conn, conn.transaction():
            # Serializes concurrent replaces for the same repo so they queue
            # rather than interleave into a partial/duplicated set.
            await conn.execute("SELECT pg_advisory_xact_lock(hashtext($1))", from_repo)

            await conn.execute(
                "DELETE FROM project_edges WHERE from_repo = $1 AND source = 'seed'",
                from_repo,
            )

            for edge in edges:
                await conn.execute(
                    """
                    INSERT INTO project_edges (from_repo, to_repo, kind, source)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (from_repo, to_repo, kind) DO NOTHING
                    """,
                    edge.from_repo,
                    edge.to_repo,
                    edge.kind.value,
                    edge.source,
                )
