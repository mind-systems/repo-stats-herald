"""Tests pinning `PerBranchSection`'s branch enumeration contract: only
branches the collector's active-branch method actually returns get
narrated, each gets its own labelled sub-part, output order follows the
collector's order, and no active branch yields `None`.
"""

from pathlib import Path

from src.changelog.sections.per_branch import PerBranchSection
from src.commits.models import Commit, CommitContext
from src.episodic.linked_change import LinkedChange


class FakeMirror:
    def object_store_path(self, repo: str) -> Path:
        return Path(f"/bare/{repo}")


class FakeCollector:
    def __init__(self, branches: list[tuple[str, str, str]]) -> None:
        self._branches = branches
        self.calls: list[tuple[str, str, str]] = []

    def active_branches(self, repo_path: str, before: str, after: str) -> list[tuple[str, str, str]]:
        self.calls.append((repo_path, before, after))
        return self._branches


class FakeResolver:
    def __init__(self, changes_by_range: dict[tuple[str, str], LinkedChange]) -> None:
        self._changes_by_range = changes_by_range
        self.calls: list[tuple[str, str, str]] = []

    def resolve(self, repo: str, before: str, after: str) -> LinkedChange:
        self.calls.append((repo, before, after))
        return self._changes_by_range[(before, after)]


class FakeReasoner:
    def __init__(self) -> None:
        self.calls: list[tuple[LinkedChange, str]] = []

    async def narrate(self, change: LinkedChange, lang: str = "ru") -> str:
        self.calls.append((change, lang))
        return f"narration-{len(self.calls)}"


def _change(repo: str, message: str) -> LinkedChange:
    commits = (Commit(sha="sha0", author="a", message=message, changed_files=(), diffstat=""),)
    return LinkedChange(
        repo=repo, completed_tasks=(), commits=CommitContext(repo=repo, branch="main", commits=commits)
    )


async def test_no_active_branch_returns_none():
    collector = FakeCollector([])
    section = PerBranchSection(FakeMirror(), collector, FakeResolver({}), FakeReasoner())

    result = await section.render("org/repo", 1, "before-sha", "after-sha")

    assert result is None
    assert collector.calls == [("/bare/org/repo", "before-sha", "after-sha")]


async def test_n_active_branches_yield_n_labelled_subparts_in_order():
    branches = [("main", "b0", "a0"), ("feature-x", "b1", "a1")]
    collector = FakeCollector(branches)
    resolver = FakeResolver(
        {
            ("b0", "a0"): _change("/bare/org/repo", "main work"),
            ("b1", "a1"): _change("/bare/org/repo", "feature work"),
        }
    )
    reasoner = FakeReasoner()
    section = PerBranchSection(FakeMirror(), collector, resolver, reasoner)

    result = await section.render("org/repo", 1, "before-sha", "after-sha")

    assert result == "### main\nnarration-1\n\n### feature-x\nnarration-2"
    assert len(reasoner.calls) == 2
    # Every narrated change is rebound to the bare KEY, matching the fix
    # SummarySection also applies before calling `narrate`.
    assert reasoner.calls[0][0].repo == "org/repo"
    assert reasoner.calls[1][0].repo == "org/repo"


async def test_branches_sharing_a_range_narrate_once_under_the_first_name():
    # An alias (`staging`) or a merged-but-undeleted feature branch pointing
    # at the same tip as `main` resolves to an identical
    # (branch_before, branch_after) range — narrate that range once, not
    # once per branch name it happens to answer to.
    branches = [("main", "b0", "a0"), ("staging", "b0", "a0"), ("feature-x", "b1", "a1")]
    collector = FakeCollector(branches)
    resolver = FakeResolver(
        {
            ("b0", "a0"): _change("/bare/org/repo", "main work"),
            ("b1", "a1"): _change("/bare/org/repo", "feature work"),
        }
    )
    reasoner = FakeReasoner()
    section = PerBranchSection(FakeMirror(), collector, resolver, reasoner)

    result = await section.render("org/repo", 1, "before-sha", "after-sha")

    assert result == "### main\nnarration-1\n\n### feature-x\nnarration-2"
    assert len(reasoner.calls) == 2
    assert resolver.calls == [("/bare/org/repo", "b0", "a0"), ("/bare/org/repo", "b1", "a1")]


async def test_branch_the_collector_omits_is_never_narrated():
    # `active_branches` is the sole source of truth for which branches are
    # "active" — a branch it doesn't return (e.g. no in-window commits)
    # never reaches the resolver/reasoner at all.
    branches = [("main", "b0", "a0")]
    collector = FakeCollector(branches)
    resolver = FakeResolver({("b0", "a0"): _change("/bare/org/repo", "main work")})
    reasoner = FakeReasoner()
    section = PerBranchSection(FakeMirror(), collector, resolver, reasoner)

    result = await section.render("org/repo", 1, "before-sha", "after-sha")

    assert result == "### main\nnarration-1"
    assert resolver.calls == [("/bare/org/repo", "b0", "a0")]
