import pytest

from src.knowledge.code_source_strategy import CodeSourceStrategy
from src.knowledge.source_strategy import AiFactorySourceStrategy

SELECTED_PATHS = [
    "src/app/service.py",
    "src/trading/order_book.ts",
    "lib/exchange/client.go",
    "app/models/user.rb",
]

NOT_SELECTED_PATHS = [
    # tests
    "tests/test_service.py",
    "src/foo/foo.test.ts",
    "src/foo/bar_test.go",
    "src/service.spec.ts",
    # vendored
    "node_modules/left-pad/index.js",
    "vendor/github.com/x/y.go",
    "src/.venv/lib/whatever.py",
    # generated
    "dist/bundle.min.js",
    "src/api/service_pb2.py",
    "src/types/index.d.ts",
    "build/main.js",
    # non-source / artifact paths
    "CLAUDE.md",
    "README.md",
    "docs/spec/x.md",
    "pyproject.toml",
]


@pytest.mark.parametrize("path", SELECTED_PATHS)
def test_selects_source_files(path: str) -> None:
    strategy = CodeSourceStrategy()

    assert strategy.selects(path) is True


@pytest.mark.parametrize("path", NOT_SELECTED_PATHS)
def test_does_not_select_excluded_or_non_source_paths(path: str) -> None:
    strategy = CodeSourceStrategy()

    assert strategy.selects(path) is False


def test_code_and_ai_factory_profiles_select_disjointly() -> None:
    code_strategy = CodeSourceStrategy()
    ai_factory_strategy = AiFactorySourceStrategy()

    assert code_strategy.selects("src/app/service.py") is True
    assert ai_factory_strategy.selects("src/app/service.py") is False

    assert ai_factory_strategy.selects(".ai-factory/ROADMAP.md") is True
    assert code_strategy.selects(".ai-factory/ROADMAP.md") is False
