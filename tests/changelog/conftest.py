import pytest

from src.changelog.report import ReportWindow
from src.changelog.section import ReportSection


class FakeSection(ReportSection):
    """Constructed with a fixed return value; `render` records every call
    as `(repo, org_id, before, after, lang)` on `calls` and returns the
    fixed value, so tests can assert every section receives the same
    range/lang the window/build call supplied."""

    def __init__(self, value: str | None) -> None:
        self._value = value
        self.calls: list[tuple[str, int, str, str, str]] = []

    async def render(
        self, repo: str, org_id: int, before: str, after: str, lang: str = "ru"
    ) -> str | None:
        self.calls.append((repo, org_id, before, after, lang))
        return self._value


class CountingWindow(ReportWindow):
    """Constructed with a fixed `(before, after)` range; `resolve`
    increments `resolve_count` and records the `repo` it was called with,
    so tests can assert the window is resolved exactly once per `build`."""

    def __init__(self, before: str, after: str) -> None:
        self._before = before
        self._after = after
        self.resolve_count = 0
        self.calls: list[str] = []

    async def resolve(self, repo: str) -> tuple[str, str]:
        self.resolve_count += 1
        self.calls.append(repo)
        return self._before, self._after


@pytest.fixture
def make_fake_section():
    def _make_fake_section(value: str | None) -> FakeSection:
        return FakeSection(value)

    return _make_fake_section


@pytest.fixture
def counting_window() -> CountingWindow:
    return CountingWindow(before="before-sha", after="after-sha")
