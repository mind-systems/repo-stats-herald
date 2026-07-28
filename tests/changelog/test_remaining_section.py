"""Tests pinning `open_tasks`' exact `[ ]`-only parse and `RemainingSection`'s
no-roadmap/no-open-task short circuits — both return `None` before any LLM
call, and only genuinely open lines ever reach the framing prompt.
"""

from pathlib import Path

from src.changelog.sections.remaining import RemainingSection, open_tasks
from src.reasoning.remaining_prompt import RemainingPromptBuilder

_MIXED_ROADMAP = """# Roadmap

- [x] **1.1 — Done task**
- [ ] **1.2 — Open task**
- [X] **1.3 — Also done (uppercase X)**
* [ ] **1.4 — Open task, star bullet**
"""

_ALL_DONE_ROADMAP = """# Roadmap

- [x] **1.1 — Done task**
- [X] **1.2 — Also done**
"""


class FakeMirror:
    def object_store_path(self, repo: str) -> Path:
        return Path(f"/bare/{repo}")


class FakeCollector:
    def __init__(self, blobs: dict[tuple[str, str], str]) -> None:
        self._blobs = blobs
        self.calls: list[tuple[str, str, str]] = []

    def read_blob(self, repo_path: str, ref: str, path: str) -> str | None:
        self.calls.append((repo_path, ref, path))
        return self._blobs.get((ref, path))


class FakeSourceStrategy:
    def __init__(self, paths: tuple[str, ...]) -> None:
        self._paths = paths

    def roadmap_paths(self) -> tuple[str, ...]:
        return self._paths


class FakeLLM:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def generate(self, prompt: str) -> str:
        self.calls.append(prompt)
        return "framed"


def test_open_tasks_matches_only_unchecked_boxes_never_x_or_capital_x():
    tasks = open_tasks(_MIXED_ROADMAP)

    assert tasks == [
        "**1.2 — Open task**",
        "**1.4 — Open task, star bullet**",
    ]


async def test_render_frames_only_open_tasks_read_at_the_after_ref():
    collector = FakeCollector({("after-sha", "ROADMAP.md"): _MIXED_ROADMAP})
    source_strategy = FakeSourceStrategy(("ROADMAP.md",))
    llm = FakeLLM()
    section = RemainingSection(FakeMirror(), collector, source_strategy, llm, RemainingPromptBuilder())

    result = await section.render("org/repo", 1, "before-sha", "after-sha")

    assert result == "framed"
    assert len(llm.calls) == 1
    prompt = llm.calls[0]
    assert "Open task" in prompt
    assert "Open task, star bullet" in prompt
    assert "Done task" not in prompt
    assert "Also done" not in prompt
    # Read at the window's end commit ("after" — the report's "now"), never
    # "before" and never a literal repo HEAD.
    assert collector.calls == [("/bare/org/repo", "after-sha", "ROADMAP.md")]


async def test_no_open_tasks_returns_none_without_calling_the_llm():
    collector = FakeCollector({("after-sha", "ROADMAP.md"): _ALL_DONE_ROADMAP})
    source_strategy = FakeSourceStrategy(("ROADMAP.md",))
    llm = FakeLLM()
    section = RemainingSection(FakeMirror(), collector, source_strategy, llm, RemainingPromptBuilder())

    result = await section.render("org/repo", 1, "before-sha", "after-sha")

    assert result is None
    assert llm.calls == []


async def test_no_roadmap_present_returns_none_without_calling_the_llm():
    collector = FakeCollector({})
    source_strategy = FakeSourceStrategy(("ROADMAP.md", ".ai-factory/ROADMAP.md"))
    llm = FakeLLM()
    section = RemainingSection(FakeMirror(), collector, source_strategy, llm, RemainingPromptBuilder())

    result = await section.render("org/repo", 1, "before-sha", "after-sha")

    assert result is None
    assert llm.calls == []
