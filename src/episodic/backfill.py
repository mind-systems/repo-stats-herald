import logging
import tempfile
from pathlib import Path

from src.commits.collector import GitCommitCollector
from src.episodic.linked_change import LinkedChangeResolver
from src.episodic.models import EpisodicEntry
from src.episodic.store import EpisodicStore
from src.github.mirror import RepoMirror
from src.knowledge.code_distiller import CodeDistiller
from src.knowledge.source_strategy import SourceStrategy
from src.llm.embedder import Embedder

logger = logging.getLogger(__name__)


class EpisodicBackfill:
    """Replays a served repo's full first-parent history, appending one
    episodic entry per historical commit with the commit's own timestamp.

    Per step, the mode is chosen fresh on harness presence: while a harness
    (roadmap) exists, the step goes through the linked-change resolver
    (resolve + embed only — no per-change LLM generation); where a step
    predates any harness, the step's entry is derived from code via
    `CodeDistiller` instead — a deliberate relaxation of the "no per-change
    LLM generation" guard for pre-harness steps, still reading changed blobs
    by SHA (no worktree). Reads the bare object store directly (no worktree
    per step), the deliberate exception to the mirror's worktree-per-operation
    model for this read-only replay. Idempotent across re-runs: a step whose
    `after` SHA is already recorded for the repo (by a prior backfill run or
    a live push) is skipped.

    Constructor DI: assembled at the composition root from the injected
    mirror, resolver, embedder, store, collector, distiller, and the two
    source strategies, plus the canonical-ref policy; it never builds a
    concrete client itself. Self-contained — calls `mirror.ensure` itself
    rather than relying on another task having run.
    """

    def __init__(
        self,
        mirror: RepoMirror,
        resolver: LinkedChangeResolver,
        embedder: Embedder,
        store: EpisodicStore,
        collector: GitCommitCollector,
        canonical_refs: dict[str, str],
        distiller: CodeDistiller,
        code_strategy: SourceStrategy,
        source_strategy: SourceStrategy,
    ) -> None:
        self._mirror = mirror
        self._resolver = resolver
        self._embedder = embedder
        self._store = store
        self._collector = collector
        self._canonical_refs = canonical_refs
        self._distiller = distiller
        self._code_strategy = code_strategy
        self._source_strategy = source_strategy

    def _canonical_ref(self, repo: str) -> str:
        override = self._canonical_refs.get(repo)
        if override is not None:
            return override
        return self._mirror.default_branch(repo)

    async def run(self, repo: str, org_id: int) -> None:
        self._mirror.ensure(repo, org_id)
        canonical = self._canonical_ref(repo)
        bare = str(self._mirror.object_store_path(repo))

        recorded = await self._store.recorded_commit_shas(repo)
        steps = self._collector.first_parent_steps(bare, canonical)

        walked = 0
        appended = 0
        skipped = 0
        for before, after in steps:
            walked += 1
            if after in recorded:
                skipped += 1
                continue

            if self._harness_present(bare, before, after):
                entry = await self._resolve_entry(repo, org_id, bare, before, after)
            else:
                entry = await self._distill_entry(repo, org_id, bare, before, after)

            if entry is None:
                logger.debug("skipping empty step: repo=%s after=%s", repo, after)
                skipped += 1
                continue

            await self._store.append(entry)
            recorded.add(after)
            appended += 1

        logger.info(
            "episodic backfill complete: repo=%s commits_walked=%d entries_appended=%d skipped=%d",
            repo,
            walked,
            appended,
            skipped,
        )

    def _harness_present(self, bare: str, before: str, after: str) -> bool:
        """A harness (roadmap) exists for this step if any of the artifact
        source strategy's roadmap candidates resolves to content at either
        end of the step. A code-only strategy's empty `roadmap_paths()`
        always yields `False`.
        """
        for path in self._source_strategy.roadmap_paths():
            for ref in (after, before):
                if self._collector.read_blob(bare, ref, path) is not None:
                    return True
        return False

    async def _resolve_entry(
        self, repo: str, org_id: int, bare: str, before: str, after: str
    ) -> EpisodicEntry | None:
        change = self._resolver.resolve(bare, before, after)
        content = "\n".join([*change.completed_tasks, *(c.message for c in change.commits.commits)])
        if not content:
            return None

        changed_at = self._collector.commit_timestamp(bare, after)
        [embedding] = await self._embedder.embed([content])

        return EpisodicEntry(
            repo=repo,
            org_id=org_id,
            completed_tasks=change.completed_tasks,
            commit_shas=tuple(c.sha for c in change.commits.commits),
            content=content,
            embedding=embedding,
            changed_at=changed_at,
        )

    async def _distill_entry(
        self, repo: str, org_id: int, bare: str, before: str, after: str
    ) -> EpisodicEntry | None:
        ctx = self._collector.collect(bare, f"{before}..{after}")

        changed = self._collector.changed_paths(bare, before, after)
        selected = [path for path in changed if self._code_strategy.selects(path)]

        written_paths: list[str] = []
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            for path in selected:
                content = self._collector.read_blob(bare, after, path)
                if content is None:
                    continue
                dest = tmp_path / path
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(content, encoding="utf-8")
                written_paths.append(path)

            distilled = (await self._distiller.distill(repo, written_paths, tmp_path)).strip() if written_paths else ""

        content = distilled or "\n".join(c.message for c in ctx.commits)
        if not content:
            return None

        changed_at = self._collector.commit_timestamp(bare, after)
        [embedding] = await self._embedder.embed([content])

        return EpisodicEntry(
            repo=repo,
            org_id=org_id,
            completed_tasks=(),
            commit_shas=tuple(c.sha for c in ctx.commits),
            content=content,
            embedding=embedding,
            changed_at=changed_at,
        )
