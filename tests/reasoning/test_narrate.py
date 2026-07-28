"""Tests pinning `Reasoner.narrate`'s silent-failure surfaces: retrieval
query construction from both `completed_tasks` and commit messages, and the
commits-only floor that guarantees `narrate` never returns empty.

Prose quality and exact prompt wording are left to the eval harness, matching
the discipline in test_reasoner_contract.py.
"""

from src.commits.models import Commit, CommitContext
from src.episodic.linked_change import LinkedChange


def _make_change(
    completed_tasks: tuple[str, ...] = (),
    commit_messages: tuple[str, ...] = ("did a thing",),
    repo: str = "api",
) -> LinkedChange:
    commits = tuple(
        Commit(sha=f"sha{i}", author="a", message=message, changed_files=(), diffstat="")
        for i, message in enumerate(commit_messages)
    )
    return LinkedChange(
        repo=repo,
        completed_tasks=completed_tasks,
        commits=CommitContext(repo=repo, branch="main", commits=commits),
    )


async def test_completed_tasks_are_included_in_the_retrieval_query(reasoner, fake_embedder):
    change = _make_change(
        completed_tasks=("8.1 — Reasoner narrate",), commit_messages=("add narrate",)
    )

    await reasoner.narrate(change)

    assert len(fake_embedder.calls) == 1
    query = fake_embedder.calls[0][0]
    assert "8.1 — Reasoner narrate" in query


async def test_commits_only_change_still_drives_retrieval(reasoner, fake_embedder):
    change = _make_change(
        completed_tasks=(), commit_messages=("fix the thing", "add the other thing")
    )

    await reasoner.narrate(change)

    query = fake_embedder.calls[0][0]
    assert "fix the thing" in query
    assert "add the other thing" in query


async def test_store_retrieval_failure_still_yields_a_non_empty_note(
    reasoner, fake_knowledge, fake_episodic
):
    fake_knowledge.error = RuntimeError("knowledge store unavailable")
    fake_episodic.error = RuntimeError("episodic store unavailable")
    change = _make_change(completed_tasks=(), commit_messages=("fix the thing",))

    result = await reasoner.narrate(change)

    assert isinstance(result, str)
    assert result


async def test_no_neighbors_yields_a_single_project_note(reasoner, fake_llm):
    change = _make_change(commit_messages=("fix the thing",))

    await reasoner.narrate(change)

    assert len(fake_llm.calls) == 1
    assert "unblocks" not in fake_llm.calls[0].lower()
