import re

from src.changelog.section import ReportSection
from src.commits.collector import GitCommitCollector
from src.github.mirror import RepoMirror
from src.knowledge.source_strategy import SourceStrategy
from src.llm.client import LLMClient
from src.reasoning.remaining_prompt import RemainingPromptBuilder

# An open roadmap task line: a `-`/`*` bullet checked with an empty `[ ]`.
# Deliberately distinct from `src/episodic/linked_change.py`'s `_DONE_LINE_RE`
# (`[xX]`) — the two regexes never overlap, so a line matches at most one of
# "done" or "open", never both.
_OPEN_LINE_RE = re.compile(r"^\s*[-*]\s*\[\s\]")


def open_tasks(content: str) -> list[str]:
    """Return the text of each open (`- [ ]`/`* [ ]`) roadmap task line in
    `content`, in file order — never a `[x]`/`[X]` line, and never via
    retrieval. The text captured is whatever follows the checkbox on the
    line (e.g. the `**N.N — subject**` portion), for prompt framing.
    """
    tasks = []
    for line in content.splitlines():
        match = _OPEN_LINE_RE.match(line)
        if match is None:
            continue
        tasks.append(line[match.end() :].strip())
    return tasks


class RemainingSection(ReportSection):
    """The "what remains open" section: reads the roadmap at the window's
    end commit (`after` — the report's "now", not literal repo `HEAD`),
    frames whatever `[ ]` tasks are still open there for readers via
    `RemainingPromptBuilder`, and returns `None` before any LLM call when
    there is no roadmap or nothing open.
    """

    def __init__(
        self,
        mirror: RepoMirror,
        collector: GitCommitCollector,
        source_strategy: SourceStrategy,
        llm: LLMClient,
        prompt: RemainingPromptBuilder,
    ) -> None:
        self._mirror = mirror
        self._collector = collector
        self._source_strategy = source_strategy
        self._llm = llm
        self._prompt = prompt

    async def render(
        self, repo: str, org_id: int, before: str, after: str, lang: str = "ru"
    ) -> str | None:
        bare = str(self._mirror.object_store_path(repo))

        content = None
        for path in self._source_strategy.roadmap_paths():
            content = self._collector.read_blob(bare, after, path)
            if content is not None:
                break
        if content is None:
            return None

        tasks = open_tasks(content)
        if not tasks:
            return None

        return await self._llm.generate(self._prompt.build(tasks, lang))
