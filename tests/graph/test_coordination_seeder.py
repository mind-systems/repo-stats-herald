from contextlib import asynccontextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Callable

from src.graph.coordination import CoordinationSeeder
from src.graph.models import Edge, EdgeKind
from src.graph.store import PgProjectGraph

ORDINARY_CLAUDE_MD = """# My Project

Some text, no coordination declared here.
"""

COORDINATION_CLAUDE_MD = """# Product Root

## Commands

| Command  | Purpose |
|----------|---------|
| make run | run it  |

## Coordination

| Member | Relationship              |
|--------|----------------------------|
| api    | contract: payments.proto  |
| auth   | auth                       |
| mobile | dependency                 |
| worker |                            |

## Other

Some trailing section, not part of Coordination.
"""


class _FakeMirror:
    """Stub `RepoMirror`: `tree` yields a scratch directory holding a
    caller-supplied `CLAUDE.md` (or none), `default_branch` returns a fixed
    ref — no real git/network involved."""

    def __init__(self, claude_md: str | None, branch: str = "main") -> None:
        self._claude_md = claude_md
        self._branch = branch

    async def default_branch(self, repo: str) -> str:
        return self._branch

    @asynccontextmanager
    async def tree(self, repo: str, org_id: int, ref: str):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            if self._claude_md is not None:
                (tmp_path / "CLAUDE.md").write_text(self._claude_md)
            yield tmp_path


def _seeder(mirror: _FakeMirror, graph: PgProjectGraph | None = None) -> CoordinationSeeder:
    return CoordinationSeeder(mirror, graph, canonical_refs={})  # type: ignore[arg-type]


def test_is_coordination_root_true_for_coordination_section() -> None:
    seeder = _seeder(_FakeMirror(None))
    assert seeder.is_coordination_root(COORDINATION_CLAUDE_MD) is True


def test_is_coordination_root_false_for_ordinary_claude_md() -> None:
    seeder = _seeder(_FakeMirror(None))
    assert seeder.is_coordination_root(ORDINARY_CLAUDE_MD) is False


def test_parse_members_maps_relationship_to_kind() -> None:
    seeder = _seeder(_FakeMirror(None))

    edges = seeder._parse_members(COORDINATION_CLAUDE_MD, "root")

    by_member = {edge.to_repo: edge for edge in edges}
    assert by_member["api"].kind == EdgeKind.CONTRACT
    assert by_member["auth"].kind == EdgeKind.AUTH
    assert by_member["mobile"].kind == EdgeKind.DEPENDENCY
    assert by_member["worker"].kind == EdgeKind.DEPENDENCY
    for edge in edges:
        assert edge.from_repo == "root"
        assert edge.source == "seed"


def test_parse_members_ignores_other_tables() -> None:
    seeder = _seeder(_FakeMirror(None))

    edges = seeder._parse_members(COORDINATION_CLAUDE_MD, "root")

    members = {edge.to_repo for edge in edges}
    assert members == {"api", "auth", "mobile", "worker"}


async def test_seed_inserts_edges_for_a_coordination_root(store: PgProjectGraph) -> None:
    seeder = CoordinationSeeder(_FakeMirror(COORDINATION_CLAUDE_MD), store, canonical_refs={"root": "main"})

    await seeder.seed("root", org_id=1)

    edges = await store.edges_from("root")
    assert {edge.to_repo for edge in edges} == {"api", "auth", "mobile", "worker"}
    assert all(edge.source == "seed" for edge in edges)


async def test_seed_removes_dropped_member(store: PgProjectGraph) -> None:
    seeder = CoordinationSeeder(_FakeMirror(COORDINATION_CLAUDE_MD), store, canonical_refs={"root": "main"})
    await seeder.seed("root", org_id=1)

    reduced_md = COORDINATION_CLAUDE_MD.replace("| mobile | dependency                 |\n", "")
    seeder_reduced = CoordinationSeeder(
        _FakeMirror(reduced_md), store, canonical_refs={"root": "main"}
    )
    await seeder_reduced.seed("root", org_id=1)

    edges = await store.edges_from("root")
    assert "mobile" not in {edge.to_repo for edge in edges}
    assert "api" in {edge.to_repo for edge in edges}


async def test_seed_drops_all_seed_edges_when_section_removed(store: PgProjectGraph) -> None:
    seeder = CoordinationSeeder(_FakeMirror(COORDINATION_CLAUDE_MD), store, canonical_refs={"root": "main"})
    await seeder.seed("root", org_id=1)

    seeder_ordinary = CoordinationSeeder(
        _FakeMirror(ORDINARY_CLAUDE_MD), store, canonical_refs={"root": "main"}
    )
    await seeder_ordinary.seed("root", org_id=1)

    edges = await store.edges_from("root")
    assert edges == []


async def test_seed_drops_all_seed_edges_when_file_missing(store: PgProjectGraph) -> None:
    seeder = CoordinationSeeder(_FakeMirror(COORDINATION_CLAUDE_MD), store, canonical_refs={"root": "main"})
    await seeder.seed("root", org_id=1)

    seeder_missing = CoordinationSeeder(_FakeMirror(None), store, canonical_refs={"root": "main"})
    await seeder_missing.seed("root", org_id=1)

    edges = await store.edges_from("root")
    assert edges == []


async def test_config_edge_survives_a_seed_cycle(
    store: PgProjectGraph, make_edge: Callable[..., Edge]
) -> None:
    config_edge = make_edge(from_repo="root", to_repo="api", kind=EdgeKind.CONTRACT, source="config")
    await store.add_edge(config_edge)

    seeder = CoordinationSeeder(_FakeMirror(COORDINATION_CLAUDE_MD), store, canonical_refs={"root": "main"})
    await seeder.seed("root", org_id=1)

    edges = await store.edges_from("root")
    api_edges = [edge for edge in edges if edge.to_repo == "api" and edge.kind == EdgeKind.CONTRACT]
    assert len(api_edges) == 1
    assert api_edges[0].source == "config"
