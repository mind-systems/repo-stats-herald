from abc import ABC, abstractmethod


class SourceStrategy(ABC):
    @abstractmethod
    def selects(self, path: str) -> bool:
        """Decide whether `path` (a repo-relative path) is one of the files
        that define the project, as opposed to noise the indexer must
        leave out."""
        ...

    def roadmap_paths(self) -> tuple[str, ...]:
        """Candidate roadmap-relative paths, in priority order, for a
        resolver that needs to read the roadmap file directly rather than
        just test membership via `selects`. A profile with no roadmap
        concept (e.g. a future code-only strategy) returns `()`, which
        callers treat as "no roadmap file exists"."""
        return ()


class AiFactorySourceStrategy(SourceStrategy):
    """The default ai-factory profile: matches the ai-factory layout, where
    the governing artifacts live under `.ai-factory/`, not only the repo
    root.

    Intended selection contract (for 3.4.2 to implement against):

    - **Selected:** `CLAUDE.md` and `AGENTS.md` at the repo root;
      `ARCHITECTURE.md` and `ROADMAP.md` whether at the root **or** under
      `.ai-factory/`; anything under `.ai-factory/specs/**`; anything under
      `docs/**`.
    - **Not selected:** the transient orchestrator artifacts — anything
      under `.ai-factory/plans/**`, `.ai-factory/plan-reviews/**`,
      `.ai-factory/reviews/**`, `.ai-factory/notes/**`,
      `.ai-factory/handoffs/**` — and code paths (e.g. `src/main.py`).

    This is the swappable per-project seam; only this default profile ships
    now, and 5.1's `CodeSourceStrategy(SourceStrategy)` extends it later.
    """

    _ROOT_ONLY = {"CLAUDE.md", "AGENTS.md"}
    _ROOT_OR_AI_FACTORY = {
        "ARCHITECTURE.md",
        "ROADMAP.md",
        ".ai-factory/ARCHITECTURE.md",
        ".ai-factory/ROADMAP.md",
    }
    _PREFIXES = (".ai-factory/specs/", "docs/")
    _ROADMAP_PATHS = ("ROADMAP.md", ".ai-factory/ROADMAP.md")

    def selects(self, path: str) -> bool:
        if path in self._ROOT_ONLY or path in self._ROOT_OR_AI_FACTORY:
            return True
        return path.startswith(self._PREFIXES)

    def roadmap_paths(self) -> tuple[str, ...]:
        return self._ROADMAP_PATHS
