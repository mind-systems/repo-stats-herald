from collections.abc import Callable

from src.graph.models import Edge, EdgeKind
from src.graph.store import PgProjectGraph


async def test_config_survives_a_colliding_seed(
    store: PgProjectGraph, make_edge: Callable[..., Edge]
) -> None:
    config_edge = make_edge(from_repo="a", to_repo="b", kind=EdgeKind.CONTRACT, source="config")
    seed_edge = make_edge(from_repo="a", to_repo="b", kind=EdgeKind.CONTRACT, source="seed")

    await store.add_edge(config_edge)
    await store.add_edge(seed_edge)

    edges = await store.edges_from("a")
    matching = [edge for edge in edges if edge.to_repo == "b" and edge.kind == EdgeKind.CONTRACT]
    assert len(matching) == 1
    assert matching[0].source == "config"


async def test_seed_only_removal(
    store: PgProjectGraph, make_edge: Callable[..., Edge]
) -> None:
    config_edge = make_edge(from_repo="a", to_repo="b", kind=EdgeKind.CONTRACT, source="config")
    seed_edge = make_edge(from_repo="a", to_repo="c", kind=EdgeKind.DEPENDENCY, source="seed")

    await store.add_edge(config_edge)
    await store.add_edge(seed_edge)

    await store.remove_seed_edges("a")

    edges = await store.edges_from("a")
    to_repos = {edge.to_repo for edge in edges}
    assert "b" in to_repos
    assert "c" not in to_repos


async def test_directed_neighbors(
    store: PgProjectGraph, make_edge: Callable[..., Edge]
) -> None:
    await store.add_edge(make_edge(from_repo="a", to_repo="b"))

    assert await store.neighbors("a") == ["b"]
    assert await store.neighbors("b") == []

    await store.add_edge(make_edge(from_repo="b", to_repo="a"))

    assert "a" in await store.neighbors("b")


async def test_idempotent_config_reload(
    store: PgProjectGraph, make_edge: Callable[..., Edge]
) -> None:
    config_edge = make_edge(from_repo="a", to_repo="b", kind=EdgeKind.CONTRACT, source="config")

    await store.add_edge(config_edge)
    await store.add_edge(config_edge)

    edges = await store.edges_from("a")
    matching = [edge for edge in edges if edge.to_repo == "b" and edge.kind == EdgeKind.CONTRACT]
    assert len(matching) == 1
