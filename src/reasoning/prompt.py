from src.episodic.models import EpisodicEntry
from src.knowledge.store import Chunk

_NO_MEMORY_TEMPLATE = (
    "Question: {query}\n\n"
    "There is no standing memory for this project — no relevant knowledge "
    "chunks and no relevant episodic entries were found. Say so honestly "
    "and do not fabricate an answer."
)

_HEADER_TEMPLATE = "Question: {query}\n\nAnswer the question below using only the memory provided.\n"

_CHUNK_SECTION_HEADER = "\nWhat the project is now (knowledge):\n"
_CHUNK_TEMPLATE = "- [{repo}{path}] {content}"

_ENTRY_SECTION_HEADER = "\nHow it changed over time (episodic history):\n"
_ENTRY_TEMPLATE = "- ({changed_at}) {content}"

_NEIGHBOR_SECTION_HEADER = "\nWhat this project relates to / unblocks (related projects):\n"
_NEIGHBOR_REPO_TEMPLATE = "\n{repo}:\n"

_INSTRUCTION_TEMPLATE = (
    "\n\nWrite grounded, feature-level prose that answers the question only "
    "from the memory above — never invent details the memory does not support."
)


class ReasoningPromptBuilder:
    """Renders a query plus retrieved memory into a plain-text prompt for an
    LLM, mirroring how PromptBuilder renders a CommitContext."""

    def build(
        self,
        query: str,
        chunks: list[Chunk],
        entries: list[EpisodicEntry],
        neighbor_chunks: list[Chunk] | None = None,
    ) -> str:
        neighbor_chunks = neighbor_chunks or []

        if not chunks and not entries and not neighbor_chunks:
            return _NO_MEMORY_TEMPLATE.format(query=query)

        sections = [_HEADER_TEMPLATE.format(query=query)]

        if chunks:
            sections.append(_CHUNK_SECTION_HEADER)
            sections.append("\n".join(self._render_chunk(chunk) for chunk in chunks))

        if entries:
            sections.append(_ENTRY_SECTION_HEADER)
            sections.append("\n".join(self._render_entry(entry) for entry in entries))

        if neighbor_chunks:
            sections.append(_NEIGHBOR_SECTION_HEADER)
            sections.append(self._render_neighbor_chunks(neighbor_chunks))

        sections.append(_INSTRUCTION_TEMPLATE)
        return "".join(sections)

    def _render_chunk(self, chunk: Chunk) -> str:
        repo = chunk.repo or ""
        path = f" {chunk.path}" if chunk.path else ""
        return _CHUNK_TEMPLATE.format(repo=repo, path=path, content=chunk.content)

    def _render_entry(self, entry: EpisodicEntry) -> str:
        return _ENTRY_TEMPLATE.format(changed_at=entry.changed_at, content=entry.content)

    def _render_neighbor_chunks(self, neighbor_chunks: list[Chunk]) -> str:
        grouped: dict[str, list[Chunk]] = {}
        for chunk in neighbor_chunks:
            repo = chunk.repo or ""
            grouped.setdefault(repo, []).append(chunk)

        groups = []
        for repo, group_chunks in grouped.items():
            group = [_NEIGHBOR_REPO_TEMPLATE.format(repo=repo)]
            group.append("\n".join(self._render_chunk(chunk) for chunk in group_chunks))
            groups.append("".join(group))

        return "".join(groups)
