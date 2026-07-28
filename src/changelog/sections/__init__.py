from src.changelog.section import ReportSection
from src.changelog.sections.per_branch import PerBranchSection
from src.changelog.sections.remaining import RemainingSection
from src.changelog.sections.summary import SummarySection
from src.commits.collector import GitCommitCollector
from src.episodic.linked_change import LinkedChangeResolver
from src.github.mirror import RepoMirror
from src.knowledge.source_strategy import SourceStrategy
from src.llm.client import LLMClient
from src.reasoning.reasoner import Reasoner
from src.reasoning.remaining_prompt import RemainingPromptBuilder


def default_section_registry(
    mirror: RepoMirror,
    resolver: LinkedChangeResolver,
    reasoner: Reasoner,
    collector: GitCommitCollector,
    source_strategy: SourceStrategy,
    llm: LLMClient,
    remaining_prompt: RemainingPromptBuilder,
) -> dict[str, ReportSection]:
    """Pin the key↔section mapping `report_for_schedule` looks up
    (`schedule.sections` entries against this registry) in one home, so a
    schedule config key can't silently drift from the section it's meant to
    select.

    Receives already-built dependencies — wiring their concrete
    implementations is the composition root's job (the future 10.2
    entrypoint), not this helper's.
    """
    return {
        "summary": SummarySection(mirror, resolver, reasoner),
        "per_branch": PerBranchSection(mirror, collector, resolver, reasoner),
        "remaining": RemainingSection(mirror, collector, source_strategy, llm, remaining_prompt),
    }
