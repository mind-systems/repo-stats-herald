import logging
import re

from src.github.mirror import RepoMirror
from src.graph.models import Edge, EdgeKind
from src.graph.store import ProjectGraph

logger = logging.getLogger(__name__)

_COORDINATION_HEADING = "## Coordination"
_SEPARATOR_CHARS = set("-: ")


class CoordinationSeeder:
    """Materializes a coordination root's `## Coordination` member table
    (see docs/behavior/coordination-root-format.md) into `source=seed`
    project-graph edges, re-seeded atomically on every canonical-ref push
    or backfill.

    Constructor DI: assembled at the composition root from the injected
    mirror and graph; it never builds a concrete client itself.
    """

    def __init__(
        self,
        mirror: RepoMirror,
        graph: ProjectGraph,
        canonical_refs: dict[str, str],
    ) -> None:
        self._mirror = mirror
        self._graph = graph
        self._canonical_refs = canonical_refs

    def is_coordination_root(self, claude_md: str) -> bool:
        return any(line.strip() == _COORDINATION_HEADING for line in claude_md.splitlines())

    def _canonical_ref(self, repo: str) -> str:
        override = self._canonical_refs.get(repo)
        if override is not None:
            return override
        return self._mirror.default_branch(repo)

    def _coordination_section(self, claude_md: str) -> list[str]:
        section: list[str] = []
        in_section = False
        for line in claude_md.splitlines():
            if line.strip() == _COORDINATION_HEADING:
                in_section = True
                continue
            if in_section and line.startswith("## "):
                break
            if in_section:
                section.append(line)
        return section

    def _boundary_trim(self, line: str) -> list[str]:
        cells = [cell.strip() for cell in line.split("|")]
        if cells and cells[0] == "":
            cells = cells[1:]
        if cells and cells[-1] == "":
            cells = cells[:-1]
        return cells

    def _is_separator_row(self, cells: list[str]) -> bool:
        return all(cell != "" and set(cell) <= _SEPARATOR_CHARS for cell in cells)

    def _edge_kind(self, relationship: str) -> EdgeKind:
        tokens = [token for token in re.split(r"[\s:]+", relationship.strip()) if token]
        first = tokens[0].lower() if tokens else ""
        if first == "contract":
            return EdgeKind.CONTRACT
        if first == "auth":
            return EdgeKind.AUTH
        return EdgeKind.DEPENDENCY

    def _parse_members(self, claude_md: str, from_repo: str) -> list[Edge]:
        edges: list[Edge] = []
        for line in self._coordination_section(claude_md):
            if "|" not in line:
                continue

            cells = self._boundary_trim(line)
            if not cells:
                continue

            member = cells[0]
            if member.lower() == "member":
                continue
            if self._is_separator_row(cells):
                continue
            if not member:
                continue

            relationship = cells[1] if len(cells) > 1 else ""
            kind = self._edge_kind(relationship)
            edges.append(Edge(from_repo=from_repo, to_repo=member, kind=kind, source="seed"))

        return edges

    async def seed(self, repo: str, org_id: int) -> None:
        canonical = self._canonical_ref(repo)

        with self._mirror.tree(repo, org_id, canonical) as tree:
            claude_md_path = tree / "CLAUDE.md"
            text = claude_md_path.read_text() if claude_md_path.is_file() else None

        is_root = text is not None and self.is_coordination_root(text)
        edges = self._parse_members(text, repo) if is_root and text is not None else []

        await self._graph.replace_seed_edges(repo, edges)

        logger.info(
            "seed complete: repo=%s ref=%s coordination_root=%s edges=%d",
            repo,
            canonical,
            is_root,
            len(edges),
        )
