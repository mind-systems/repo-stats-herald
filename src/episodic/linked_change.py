from dataclasses import dataclass

from src.commits.collector import GitCommitCollector
from src.commits.models import CommitContext
from src.knowledge.source_strategy import SourceStrategy


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

        Intended contract (implemented by the follow-up task; this is a stub):

        - `completed_tasks` is the roadmap's done-marker set at `after` minus
          the done-marker set at `before` — a set-difference over the two
          full roadmap versions, NOT a scan of the diff for added `+[x]`
          lines.
        - Each done marker is keyed by the stable leading `N.N.N` task
          identifier on a `[x]` roadmap line (e.g. the `4.2.1` in
          `- [x] **4.2.1 — …**`), never by the full line text. Keying on the
          identifier means a task line that moves, is re-indented, or is
          reworded within the range keeps the same key, so a line that was
          already `[x]` at `before` and merely relocates appears in both the
          `before` and `after` sets and cancels out of the difference — it is
          not miscounted as newly completed. A `[x]` line with no `N.N.N`
          identifier is not a keyable done-marker.
        - The roadmap path is chosen via the injected `SourceStrategy`
          (default `ROADMAP.md`, or `.ai-factory/ROADMAP.md` if present) —
          never hardcoded to a single path.
        - `commits` comes from `GitCommitCollector.collect(repo, f"{before}..{after}")`.
        - No roadmap file at either ref, or no genuine done-transition in the
          range, yields an empty `completed_tasks` and falls back to
          commits-only — this must never crash, including over merge commits
          or an empty range (`before == after`).
        """
        raise NotImplementedError
