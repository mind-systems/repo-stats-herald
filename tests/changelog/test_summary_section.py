"""Tests pinning `SummarySection`'s empty-window short-circuit and the
`dataclasses.replace` repo-key rebind before `Reasoner.narrate` — the fix
that keeps narration retrieval scoped to the bare repo KEY instead of the
resolver's filesystem path.
"""

from pathlib import Path

from src.changelog.sections.summary import SummarySection
from src.commits.models import Commit, CommitContext
from src.episodic.linked_change import LinkedChange


class FakeMirror:
    def object_store_path(self, repo: str) -> Path:
        return Path(f"/bare/{repo}")


class FakeResolver:
    """Returns a fixed `LinkedChange` (built against the bare filesystem
    path, mirroring the resolver's real behavior) regardless of the range
    it is asked to resolve; records every call."""

    def __init__(self, change: LinkedChange) -> None:
        self._change = change
        self.calls: list[tuple[str, str, str]] = []

    def resolve(self, repo: str, before: str, after: str) -> LinkedChange:
        self.calls.append((repo, before, after))
        return self._change


class FakeReasoner:
    def __init__(self, result: str = "narrated") -> None:
        self._result = result
        self.calls: list[tuple[LinkedChange, str]] = []

    async def narrate(self, change: LinkedChange, lang: str = "ru") -> str:
        self.calls.append((change, lang))
        return self._result


def _change(repo: str, commit_messages: tuple[str, ...]) -> LinkedChange:
    commits = tuple(
        Commit(sha=f"sha{i}", author="a", message=message, changed_files=(), diffstat="")
        for i, message in enumerate(commit_messages)
    )
    return LinkedChange(
        repo=repo, completed_tasks=(), commits=CommitContext(repo=repo, branch="main", commits=commits)
    )


async def test_empty_window_returns_none_without_narrating():
    # The resolver's `.repo` reflects the bare filesystem path it actually
    # ran git against — realistic ground truth for what `resolve` returns
    # before any rebind.
    empty_change = _change("/bare/org/repo", commit_messages=())
    resolver = FakeResolver(empty_change)
    reasoner = FakeReasoner()
    section = SummarySection(FakeMirror(), resolver, reasoner)

    result = await section.render("org/repo", 1, "before-sha", "after-sha")

    assert result is None
    assert reasoner.calls == []
    assert resolver.calls == [("/bare/org/repo", "before-sha", "after-sha")]


async def test_non_empty_window_narrates_with_repo_key_rebound():
    change = _change("/bare/org/repo", commit_messages=("did a thing",))
    resolver = FakeResolver(change)
    reasoner = FakeReasoner(result="the shipped story")
    section = SummarySection(FakeMirror(), resolver, reasoner)

    result = await section.render("org/repo", 1, "before-sha", "after-sha", lang="de")

    assert result == "the shipped story"
    assert len(reasoner.calls) == 1
    narrated_change, lang = reasoner.calls[0]
    # Rebound to the bare KEY the caller passed in, not the resolver's
    # filesystem path — otherwise narration retrieval scopes to a key with
    # zero rows.
    assert narrated_change.repo == "org/repo"
    assert lang == "de"
