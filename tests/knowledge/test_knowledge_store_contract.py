from collections.abc import Callable

import asyncpg

from src.knowledge.store import Chunk, PgVectorStore

EMBEDDING_DIM = 768


def _unit_vector(axis: int, value: float = 1.0) -> list[float]:
    vector = [0.0] * EMBEDDING_DIM
    vector[axis] = value
    return vector


async def test_query_orders_results_nearest_first_by_cosine(
    store: PgVectorStore, make_chunk: Callable[..., Chunk]
) -> None:
    repo, path = "org/repo", "a.py"
    nearest = make_chunk("nearest", axis=0, value=1.0)  # same direction as query -> distance 0
    middle = make_chunk("middle", axis=1, value=1.0)  # orthogonal to query -> distance 1
    farthest = make_chunk("farthest", axis=0, value=-1.0)  # opposite of query -> distance 2

    await store.upsert(repo, path, [nearest, middle, farthest])

    results = await store.query(_unit_vector(axis=0), k=3, repo=repo)

    assert results[0].content == "nearest"
    assert results[1].content == "middle"
    assert results[2].content == "farthest"


async def test_upsert_atomically_replaces_prior_chunks_for_the_path(
    store: PgVectorStore, pg_pool: asyncpg.Pool, make_chunk: Callable[..., Chunk]
) -> None:
    repo, path = "org/repo", "b.py"
    original = [make_chunk(f"orig-{i}", axis=i) for i in range(5)]
    await store.upsert(repo, path, original)

    replacement = [make_chunk(f"new-{i}", axis=i) for i in range(2)]
    await store.upsert(repo, path, replacement)

    rows = await pg_pool.fetch(
        "SELECT chunk_index FROM chunks WHERE repo = $1 AND path = $2 ORDER BY chunk_index",
        repo,
        path,
    )
    assert [row["chunk_index"] for row in rows] == [0, 1]


async def test_delete_removes_only_the_scoped_path(
    store: PgVectorStore, pg_pool: asyncpg.Pool, make_chunk: Callable[..., Chunk]
) -> None:
    repo, other_repo = "org/repo", "org/other-repo"
    path_a, path_b = "a.py", "b.py"

    await store.upsert(repo, path_a, [make_chunk("a0", axis=0)])
    await store.upsert(repo, path_b, [make_chunk("b0", axis=1)])
    await store.upsert(other_repo, path_a, [make_chunk("other-a0", axis=2)])

    await store.delete(repo, path_a)

    rows = await pg_pool.fetch("SELECT repo, path FROM chunks ORDER BY repo, path")
    remaining = {(row["repo"], row["path"]) for row in rows}
    assert remaining == {(repo, path_b), (other_repo, path_a)}
