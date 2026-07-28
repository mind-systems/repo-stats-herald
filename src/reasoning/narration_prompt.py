from src.episodic.linked_change import LinkedChange
from src.episodic.models import EpisodicEntry
from src.knowledge.store import Chunk

_TASKS_HEADER_TEMPLATE = (
    "Repository: {repo}\n\n"
    "Completed roadmap tasks:\n{tasks}\n\n"
    "Write a narration that leads with what these completed tasks delivered "
    "(intent and outcome). The commits below are supporting detail, not the "
    "lead.\n"
)

_DIGEST_HEADER_TEMPLATE = (
    "Repository: {repo}\n\n"
    "No roadmap tasks were completed in this change. Anchor the narration on "
    "a coherent digest of the commits below — describe what changed at the "
    "feature level, never fabricating a completed feature.\n"
)

_TASK_TEMPLATE = "- {task}"

_COMMITS_SECTION_HEADER = "\nCommits:\n"
_COMMIT_TEMPLATE = "- {message}"

_CHUNK_SECTION_HEADER = "\nWhat the project is now (knowledge):\n"
_CHUNK_TEMPLATE = "- [{repo}{path}] {content}"

_ENTRY_SECTION_HEADER = "\nHow it changed over time (episodic history):\n"
_ENTRY_TEMPLATE = "- ({changed_at}) {content}"

_NEIGHBOR_SECTION_HEADER = "\nWhat this change unblocks elsewhere (related projects):\n"
_NEIGHBOR_REPO_TEMPLATE = "\n{repo}:\n"

_INSTRUCTION_TEMPLATE = (
    "\n\nWrite grounded, feature-level prose narrating this change — never "
    "bullets, never a raw diff — in {lang}."
)


class NarrationPromptBuilder:
    """Renders a resolved LinkedChange plus retrieved memory into a
    plain-text narration prompt for an LLM, mirroring how
    ReasoningPromptBuilder renders retrieved memory for Q&A — framed as
    narration (completed tasks lead, commits are supporting detail,
    cross-project neighbors are framed as what the change "unblocks")
    rather than as an answer to a question."""

    def build(
        self,
        change: LinkedChange,
        chunks: list[Chunk],
        entries: list[EpisodicEntry],
        neighbor_chunks: list[Chunk],
        lang: str = "ru",
    ) -> str:
        if change.completed_tasks:
            tasks = "\n".join(_TASK_TEMPLATE.format(task=task) for task in change.completed_tasks)
            header = _TASKS_HEADER_TEMPLATE.format(repo=change.repo, tasks=tasks)
        else:
            header = _DIGEST_HEADER_TEMPLATE.format(repo=change.repo)

        sections = [header]

        commits = "\n".join(
            _COMMIT_TEMPLATE.format(message=commit.message) for commit in change.commits.commits
        )
        sections.append(_COMMITS_SECTION_HEADER)
        sections.append(commits)

        if chunks:
            sections.append(_CHUNK_SECTION_HEADER)
            sections.append("\n".join(self._render_chunk(chunk) for chunk in chunks))

        if entries:
            sections.append(_ENTRY_SECTION_HEADER)
            sections.append("\n".join(self._render_entry(entry) for entry in entries))

        if neighbor_chunks:
            sections.append(_NEIGHBOR_SECTION_HEADER)
            sections.append(self._render_neighbor_chunks(neighbor_chunks))

        sections.append(_INSTRUCTION_TEMPLATE.format(lang=lang))
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
