from abc import ABC, abstractmethod
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import timedelta

from src.changelog.section import ReportSection
from src.core.config import ReportSchedule


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
    `delta` of history. Equality is by `delta` alone."""

    delta: timedelta

    async def resolve(self, repo: str) -> tuple[str, str]:
        raise NotImplementedError(
            "TimeWindow.resolve (git range over the mirror) lands with the 10.2 entrypoint"
        )


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


def report_for_schedule(schedule: ReportSchedule, registry: Mapping[str, ReportSection]) -> Report:
    """Build the `Report` a schedule describes: a `TimeWindow` sized by
    `schedule.window` days, and each of `schedule.sections` looked up in
    `registry`, in order.

    Raises `ValueError` naming the first section key in `schedule.sections`
    that is absent from `registry` — the composition root's startup error
    for a misconfigured schedule.
    """
    window = TimeWindow(timedelta(days=schedule.window))

    sections = []
    for key in schedule.sections:
        if key not in registry:
            raise ValueError(f"unknown report section {key!r} in schedule {schedule.name!r}")
        sections.append(registry[key])

    return Report(window, sections)
