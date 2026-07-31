import logging
from pathlib import Path

from src.github.mirror import RepoMirror
from src.knowledge.code_distiller import CodeDistiller
from src.knowledge.source_strategy import AiFactorySourceStrategy, SourceStrategy

logger = logging.getLogger(__name__)

# The single non-selected path bootstrap ever writes — repo-relative leaf under
# `draft_root/<repo>/`. Never `KnowledgeStore`-indexed, never a source-selected
# path, never a committed artifact.
_DRAFT_RELPATH = ".ai-factory/bootstrap-draft.md"


class CodeBootstrap:
    """Distills a code-only repo's current HEAD into a feature-level draft
    written to a fixed, source-strategy-excluded path, giving the repo a path
    into the knowledge store without ever writing it directly.

    The draft is for a human to review and graduate into a committed,
    curated **selected** artifact — this class never touches `KnowledgeStore`
    and never writes anywhere except its own fixed draft leaf.

    Constructor DI, matching `KnowledgeSync` in `src/knowledge/sync.py`: no
    concretes are built inside. `mirror` and `distiller` stay concrete (they
    have no ABC); `strategy` is typed as the `SourceStrategy` abstraction
    since only its `selects` method is called here — the composition root
    injects the concrete `CodeSourceStrategy()`.
    """

    def __init__(
        self,
        mirror: RepoMirror,
        distiller: CodeDistiller,
        strategy: SourceStrategy,
        draft_root: Path,
    ) -> None:
        if AiFactorySourceStrategy().selects(_DRAFT_RELPATH):
            raise RuntimeError(
                f"{_DRAFT_RELPATH!r} is selected by AiFactorySourceStrategy — "
                "the bootstrap draft would become auto-indexable, which must never happen"
            )

        self._mirror = mirror
        self._distiller = distiller
        self._strategy = strategy
        self._draft_root = draft_root

    async def run(self, repo: str, org_id: int) -> Path:
        """Distill `repo`'s current HEAD into a draft and write it under
        `draft_root/<repo>/.ai-factory/bootstrap-draft.md`, overwriting any
        prior draft at that path (idempotent, no duplication). Returns the
        written path."""
        ref = "HEAD"
        await self._mirror.ensure(repo, org_id)

        async with self._mirror.tree(repo, org_id, ref) as tree:
            selected = []
            for path in tree.rglob("*"):
                if not path.is_file() or ".git" in path.parts:
                    continue
                rel = path.relative_to(tree).as_posix()
                if self._strategy.selects(rel):
                    selected.append(rel)

            distilled = await self._distiller.distill(repo, selected, tree)

        framed = self._frame(distilled)

        draft_path = self._draft_root / repo / _DRAFT_RELPATH
        draft_path.parent.mkdir(parents=True, exist_ok=True)
        draft_path.write_text(framed, encoding="utf-8")

        logger.info(
            "bootstrap complete: repo=%s ref=%s selected_files=%d draft_path=%s",
            repo,
            ref,
            len(selected),
            draft_path,
        )
        return draft_path

    def _frame(self, body: str) -> str:
        """Wrap the distiller's raw output in a title plus an unmistakable
        LLM-generated/unreviewed banner. The banner instructs a human reader
        that this file is an automated draft, is NOT indexed into the
        knowledge store, and must be reviewed and its content copied/adapted
        into a curated selected artifact and committed — this file itself is
        never committed as-is."""
        return (
            "# Bootstrap draft — automated, unreviewed\n\n"
            "> **This file is a machine-generated draft.** It was distilled "
            "automatically from the repository's source code and has not been "
            "reviewed by a human. It is NOT indexed into the knowledge store and "
            "carries no authority on its own.\n"
            ">\n"
            "> A human must review this draft, then copy and adapt the parts that "
            "hold up into a curated, selected artifact and commit that artifact. "
            "This draft file itself must never be committed as-is.\n\n"
            f"{body}\n"
        )
