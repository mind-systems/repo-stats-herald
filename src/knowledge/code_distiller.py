import logging
import os
from dataclasses import dataclass
from pathlib import Path

from src.llm.client import LLMClient

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CodeUnit:
    """A single bounded grouping of paths sharing one module key — the unit
    that 5.2.2 turns into exactly one LLM prompt, so a codebase of M
    modules never collapses into one unbounded prompt."""

    module: str
    paths: tuple[str, ...]


# The distillation rubric — copied verbatim from "What counts as a feature —
# the distillation rubric" (see docs/concepts/code-derived-understanding.md).
# The implementation authors none of its own criteria here.
_DISCRIMINATOR = (
    "Discriminator: could you write an end-to-end test for this that didn't exist "
    "before? Yes — it is a feature: any verifiable interaction counts (user-to-system, "
    "system-to-system, system-to-external-service, or an internal subsystem with its "
    "own behaviour contract). No — it is internal (a refactor, a cleanup, plumbing) "
    "and must stay out of the description."
)

_NAMING = (
    "Naming: name each feature in 2-5 words from the operator's perspective — what "
    "the system can do, never how it is built. Module and directory names must never "
    "become feature names. Prefer fewer, larger cross-cutting features over one "
    "feature per module."
)

_GENRE = (
    "Genre: write present-tense delivered behaviour — state what the project does, "
    "never how it came to be. Do not write in a history or process voice "
    '("was added", "was replaced", "previously", "this milestone"). Do not dump '
    'symbols or mechanism ("class X has methods Y, Z", call-chain listings).'
)

_PROMPT_TEMPLATE = (
    "You are distilling the source code of module {module!r} into a feature-level "
    "description.\n\n"
    "{discriminator}\n\n"
    "{naming}\n\n"
    "{genre}\n\n"
    "Code:\n{code}\n\n"
    "Write the feature description now."
)


class CodeDistiller:
    """Turns a selected set of a repo's source paths into one feature-level
    description, bounded per package/module rather than issued as a single
    whole-codebase prompt.

    The model-agnostic swap seam is the injected `LLMClient` — this class
    never constructs a concrete client itself; a composition root injects
    one."""

    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    async def distill(self, repo: str, paths: list[str], tree: Path) -> str:
        """Distill `paths` from `repo`'s mirror `tree` into one composed
        description.

        Groups `paths` into bounded `CodeUnit`s via `group_units`, reads each
        unit's files from `tree` (skipping any path that isn't valid UTF-8),
        prompts the injected `LLMClient` once per unit with content to
        distill, then joins the per-unit descriptions with `compose`. A unit
        with no readable content issues no LLM call.
        """
        units = self.group_units(paths)

        unit_texts: list[str] = []
        for unit in units:
            file_blobs = []
            for path in unit.paths:
                try:
                    text = (tree / path).read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    logger.debug("skipping %s:%s — not valid UTF-8", repo, path)
                    continue
                file_blobs.append(f"# {path}\n{text}")

            if not file_blobs:
                logger.debug(
                    "skipping unit %s:%s — no readable content", repo, unit.module
                )
                continue

            code = "\n\n".join(file_blobs)
            prompt = self._build_prompt(unit, code)
            desc = await self._llm.generate(prompt)
            unit_texts.append(desc)

        return self.compose(unit_texts)

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
        by_module: dict[str, list[str]] = {}
        for path in paths:
            module = os.path.dirname(path)
            by_module.setdefault(module, []).append(path)

        return [
            CodeUnit(module=module, paths=tuple(sorted(by_module[module])))
            for module in sorted(by_module)
        ]

    def compose(self, unit_texts: list[str]) -> str:
        """Concatenate per-unit description strings, in the given order,
        joined by a blank line (`"\\n\\n"`).

        Deterministic: the same `unit_texts` in the same order always
        produces the same byte-identical output. Callers pass unit texts in
        the order `group_units` returned them, so the composed result is
        stable across runs regardless of the original path order.
        """
        return "\n\n".join(unit_texts)

    def _build_prompt(self, unit: CodeUnit, code: str) -> str:
        return _PROMPT_TEMPLATE.format(
            module=unit.module,
            discriminator=_DISCRIMINATOR,
            naming=_NAMING,
            genre=_GENRE,
            code=code,
        )
