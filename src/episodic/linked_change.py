import re
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass

from src.commits.collector import GitCommitCollector
from src.commits.models import CommitContext
from src.knowledge.source_strategy import SourceStrategy

# A roadmap line counts as "done" when it is a `-`/`*` bullet checked with
# `[x]` (case-insensitive); a `[ ]` bullet is not done.
_DONE_LINE_RE = re.compile(r"^\s*[-*]\s*\[[xX]\]")
# The stable leading task identifier on a done line, e.g. the `4.2.1` in
# `- [x] **4.2.1 — …**`. A bare phase number like `4` has no dot and is not
# a keyable identifier.
_TASK_ID_RE = re.compile(r"\d+(?:\.\d+)+")


@dataclass(frozen=True, slots=True)
class LinkedChange:
    repo: str
    completed_tasks: tuple[str, ...]
    commits: CommitContext


class LinkedChangeResolver:
    """Resolves a push's range to the roadmap intent it delivered plus the
    commits that delivered it."""

    def __init__(self, collector: GitCommitCollector, source_strategy: SourceStrategy) -> None:
        self._collector = collector
        self._source_strategy = source_strategy

    def resolve(self, repo: str, before: str, after: str) -> LinkedChange:
        """Resolve `repo`'s `before..after` range to a `LinkedChange`.

        `completed_tasks` is the roadmap's done-marker set at `after` minus
        the done-marker set at `before` — a set-difference over the two full
        roadmap versions, not a scan of the diff for added `+[x]` lines. A
        task identifier already done at `before` that merely relocates,
        reformats, or is reworded within the range appears in both sets and
        cancels out. The roadmap path is the first candidate from the
        injected `SourceStrategy` that is present at either ref; if none is
        present, or no genuine done-transition occurred, `completed_tasks`
        is empty and only `commits` (from `GitCommitCollector`) is
        populated. This never raises, including over merge commits or an
        empty range (`before == after`).
        """
        before_content, after_content = self._read_roadmap_versions(repo, before, after)

        before_done = self._done_identifiers(before_content or "")
        seen: set[str] = set()
        completed_tasks: list[str] = []
        for identifier in self._iter_done_identifiers(after_content or ""):
            if identifier in before_done or identifier in seen:
                continue
            seen.add(identifier)
            completed_tasks.append(identifier)

        commits = self._collector.collect(repo, f"{before}..{after}")

        return LinkedChange(repo=repo, completed_tasks=tuple(completed_tasks), commits=commits)

    def _read_roadmap_versions(self, repo: str, before: str, after: str) -> tuple[str | None, str | None]:
        for path in self._source_strategy.roadmap_paths():
            before_content = self._read_roadmap_at(repo, before, path)
            after_content = self._read_roadmap_at(repo, after, path)
            if before_content is not None or after_content is not None:
                return before_content, after_content
        return None, None

    def _read_roadmap_at(self, repo: str, ref: str, path: str) -> str | None:
        result = subprocess.run(
            ["git", "-C", repo, "show", "--end-of-options", f"{ref}:{path}"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return None
        return result.stdout

    def _iter_done_identifiers(self, content: str) -> Iterator[str]:
        for line in content.splitlines():
            if not _DONE_LINE_RE.match(line):
                continue
            match = _TASK_ID_RE.search(line)
            if match is not None:
                yield match.group(0)

    def _done_identifiers(self, content: str) -> set[str]:
        return set(self._iter_done_identifiers(content))
