from abc import ABC, abstractmethod
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from src.changelog.section import ReportSection
from src.commits.collector import EMPTY_TREE_SHA, GitCommitCollector
from src.core.config import ReportSchedule
from src.github.mirror import RepoMirror, resolve_canonical_ref


class ReportWindow(ABC):
    """The seam that resolves a report's commit range on demand.

    `resolve` carries no `org_id` by design — a window is a pure function of
    `repo` and its own configuration. It never calls `mirror.ensure`; the
    bare mirror is already ensured by the caller before `resolve` runs.
    """

    @abstractmethod
    async def resolve(self, repo: str) -> tuple[str, str]:
        """Return the `(before, after)` commit range for `repo` on the
        already-ensured bare mirror."""
        ...


@dataclass(frozen=True)
class TimeWindow(ReportWindow):
    """A `ReportWindow` that resolves to the commit range covering the last
    `delta` of history, anchored on the repo's canonical ref and
    wall-clock-relative (`datetime.now(timezone.utc)`) at resolution time.
    Equality is by `delta` alone — the collaborators below are wiring, not
    identity."""

    delta: timedelta
    mirror: RepoMirror | None = field(default=None, compare=False)
    collector: GitCommitCollector | None = field(default=None, compare=False)
    canonical_refs: dict[str, str] | None = field(default=None, compare=False)

    async def resolve(self, repo: str) -> tuple[str, str]:
        if self.mirror is None or self.collector is None or self.canonical_refs is None:
            raise RuntimeError(
                "TimeWindow is missing its mirror/collector/canonical_refs collaborators "
                "— an unwired window is a composition-root bug"
            )

        ref = await resolve_canonical_ref(repo, self.canonical_refs, self.mirror)
        bare = str(self.mirror.object_store_path(repo))

        now = datetime.now(timezone.utc)
        after = self.collector.commit_at_or_before(bare, ref, now)
        before = self.collector.commit_at_or_before(bare, ref, now - self.delta)

        if after is None:
            return EMPTY_TREE_SHA, EMPTY_TREE_SHA
        if before is None:
            before = EMPTY_TREE_SHA

        return before, after


class Report:
    """Composes an ordered list of `ReportSection`s over a single
    `ReportWindow`.

    `build` resolves the window exactly once per call — every section sees
    the same `(before, after)` range. Sections that return `None` are
    dropped (never rendered as `""` or the literal `"None"`); if every
    section returns `None`, `build` returns `None`. Otherwise the surviving
    section texts are joined with `"\\n\\n"` into a single string.
    """

    def __init__(self, window: ReportWindow, sections: list[ReportSection]) -> None:
        self.window = window
        self.sections = sections

    async def build(self, repo: str, org_id: int, lang: str = "ru") -> str | None:
        before, after = await self.window.resolve(repo)

        texts = []
        for section in self.sections:
            text = await section.render(repo, org_id, before, after, lang)
            if text is not None:
                texts.append(text)

        if not texts:
            return None
        return "\n\n".join(texts)


def schedule_by_name(schedules: Iterable[ReportSchedule], name: str) -> ReportSchedule:
    """Return the schedule in `schedules` whose `name` matches; raise
    `ValueError` if none does."""
    for schedule in schedules:
        if schedule.name == name:
            return schedule
    raise ValueError(f"no report schedule named {name!r}")


def report_for_schedule(
    schedule: ReportSchedule,
    registry: Mapping[str, ReportSection],
    *,
    mirror: RepoMirror | None = None,
    collector: GitCommitCollector | None = None,
    canonical_refs: dict[str, str] | None = None,
) -> Report:
    """Build the `Report` a schedule describes: a `TimeWindow` sized by
    `schedule.window` days, and each of `schedule.sections` looked up in
    `registry`, in order.

    `mirror`/`collector`/`canonical_refs` are keyword-only and default to
    `None` so the window builds unwired for equality-only tests; the
    composition root passes the real collaborators so `TimeWindow.resolve`
    can run.

    Raises `ValueError` naming the first section key in `schedule.sections`
    that is absent from `registry` — the composition root's startup error
    for a misconfigured schedule.
    """
    window = TimeWindow(
        timedelta(days=schedule.window),
        mirror=mirror,
        collector=collector,
        canonical_refs=canonical_refs,
    )

    sections = []
    for key in schedule.sections:
        if key not in registry:
            raise ValueError(f"unknown report section {key!r} in schedule {schedule.name!r}")
        sections.append(registry[key])

    return Report(window, sections)
