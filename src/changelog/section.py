from abc import ABC, abstractmethod


class ReportSection(ABC):
    """One self-contained content block of a report, rendered over an
    already-resolved `(before, after)` commit range.

    The caller (`Report`) resolves the range once per report build and the
    bare mirror is already ensured before a section is ever rendered — a
    section never calls `mirror.ensure` itself, and never resolves its own
    range.
    """

    @abstractmethod
    async def render(
        self, repo: str, org_id: int, before: str, after: str, lang: str = "ru"
    ) -> str | None:
        """Render this section's text for `repo` over the `(before, after)`
        range, in `lang`. Returns `None` when this section has nothing to
        say for that range — never an empty string."""
        ...
