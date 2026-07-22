import pytest

from src.knowledge.source_strategy import AiFactorySourceStrategy

SELECTED_PATHS = [
    "CLAUDE.md",
    "AGENTS.md",
    "ARCHITECTURE.md",
    "ROADMAP.md",
    ".ai-factory/ARCHITECTURE.md",
    ".ai-factory/ROADMAP.md",
    ".ai-factory/specs/43-source-strategy-chunker-contract.md",
    "docs/spec/understanding.md",
    "docs/architecture.md",
]

NOT_SELECTED_PATHS = [
    ".ai-factory/plans/17-x.md",
    ".ai-factory/plan-reviews/x.md",
    ".ai-factory/reviews/x.md",
    ".ai-factory/notes/01-x.md",
    ".ai-factory/handoffs/x.md",
    "src/main.py",
    "src/knowledge/store.py",
]


@pytest.mark.parametrize("path", SELECTED_PATHS)
def test_selects_project_defining_paths(path: str) -> None:
    strategy = AiFactorySourceStrategy()

    assert strategy.selects(path) is True


@pytest.mark.parametrize("path", NOT_SELECTED_PATHS)
def test_does_not_select_orchestrator_noise_and_code(path: str) -> None:
    strategy = AiFactorySourceStrategy()

    assert strategy.selects(path) is False
