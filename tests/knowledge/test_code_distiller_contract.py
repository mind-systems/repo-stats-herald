"""Red tests pinning `CodeDistiller.group_units`'s and `CodeDistiller.compose`'s
bounded-unit grouping and composition semantics against the stub.

Every test below calls `group_units`/`compose` as if they were already
implemented and asserts on the result; each fails only because the stub
raises `NotImplementedError` — never because of an import, fixture, or
signature mismatch. The follow-up task's grouping/composition
implementation turns these green unchanged.
"""

import pytest

from src.knowledge.code_distiller import CodeDistiller, CodeUnit
from src.llm.client import LLMClient


class FakeLLMClient(LLMClient):
    """Records every prompt it is given and returns a deterministic
    per-call marker — the injected boundary that proves the pure
    grouping/composition seam never awaits a model call."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def generate(self, prompt: str) -> str:
        self.calls.append(prompt)
        return f"desc:{len(self.calls)}"


@pytest.fixture
def fake_llm() -> FakeLLMClient:
    return FakeLLMClient()


@pytest.fixture
def distiller(fake_llm: FakeLLMClient) -> CodeDistiller:
    return CodeDistiller(fake_llm)


def test_unit_count_matches_module_count(distiller):
    # 4 paths spanning 3 distinct modules — "src/a" has two files, so the
    # unit count must track distinct modules, not distinct paths.
    paths = [
        "src/a/one.py",
        "src/a/two.py",
        "src/b/one.py",
        "src/c/one.py",
    ]

    units = distiller.group_units(paths)

    assert len(units) == 3
    for unit in units:
        assert isinstance(unit, CodeUnit)
        parents = {path.rsplit("/", 1)[0] if "/" in path else "" for path in unit.paths}
        assert len(parents) == 1
    assert all(len(unit.paths) < len(paths) for unit in units)


def test_grouping_is_full_and_disjoint(distiller):
    paths = [
        "src/a/one.py",
        "src/a/two.py",
        "src/b/one.py",
        "readme.md",
    ]

    units = distiller.group_units(paths)

    covered: list[str] = []
    for unit in units:
        covered.extend(unit.paths)

    assert sorted(covered) == sorted(paths)
    assert len(covered) == len(paths)
    assert len(set(covered)) == len(paths)


def test_composition_is_stable_and_ordered(distiller):
    unit_texts = ["unit-a", "unit-b", "unit-c"]

    first = distiller.compose(unit_texts)
    second = distiller.compose(unit_texts)

    assert first == "unit-a\n\nunit-b\n\nunit-c"
    assert first == second


def test_grouping_order_is_sorted_by_module(distiller):
    # Deliberately unsorted input order.
    paths = [
        "src/c/one.py",
        "src/a/two.py",
        "src/b/one.py",
        "src/a/one.py",
    ]

    units = distiller.group_units(paths)

    assert [unit.module for unit in units] == ["src/a", "src/b", "src/c"]
    for unit in units:
        assert list(unit.paths) == sorted(unit.paths)


def test_pure_seam_issues_no_model_call(distiller, fake_llm):
    paths = ["src/a/one.py", "src/b/one.py"]

    units = distiller.group_units(paths)
    distiller.compose([f"desc for {unit.module}" for unit in units])

    assert fake_llm.calls == []
