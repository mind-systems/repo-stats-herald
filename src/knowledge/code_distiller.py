from dataclasses import dataclass

from src.llm.client import LLMClient


@dataclass(frozen=True)
class CodeUnit:
    """A single bounded grouping of paths sharing one module key — the unit
    that 5.2.2 turns into exactly one LLM prompt, so a codebase of M
    modules never collapses into one unbounded prompt."""

    module: str
    paths: tuple[str, ...]


class CodeDistiller:
    """Turns a selected set of a repo's source paths into one feature-level
    description, bounded per package/module rather than issued as a single
    whole-codebase prompt.

    The model-agnostic swap seam is the injected `LLMClient` — this class
    never constructs a concrete client itself; a composition root injects
    one."""

    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    async def distill(self, repo: str, paths: list[str]) -> str:
        """Distill `paths` from `repo` into one composed description.

        The eventual flow: group `paths` into bounded `CodeUnit`s via
        `group_units`, read and prompt the injected `LLMClient` once per
        unit from the repo's mirror, then join the per-unit descriptions
        with `compose`. Per-unit LLM-output quality is out of scope here —
        that is the follow-up task's concern; this method only orchestrates
        the bounded-prompt shape.
        """
        raise NotImplementedError

    def group_units(self, paths: list[str]) -> list[CodeUnit]:
        """Group `paths` into bounded `CodeUnit`s, one per module.

        A path's module is its parent directory — `os.path.dirname(path)`
        (a repo-root file's module is `""`). Every path sharing a parent
        directory belongs to exactly one unit, so a codebase spanning M
        distinct modules always yields exactly M units — never one giant
        unit holding the whole codebase. The result is the full, disjoint
        partition of the input: every input path appears in exactly one
        unit's `paths`. Units are sorted by module key ascending; paths
        within a unit are sorted ascending — a deterministic order that
        downstream composition relies on.
        """
        raise NotImplementedError

    def compose(self, unit_texts: list[str]) -> str:
        """Concatenate per-unit description strings, in the given order,
        joined by a blank line (`"\\n\\n"`).

        Deterministic: the same `unit_texts` in the same order always
        produces the same byte-identical output. Callers pass unit texts in
        the order `group_units` returned them, so the composed result is
        stable across runs regardless of the original path order.
        """
        raise NotImplementedError
