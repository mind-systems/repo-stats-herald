"""Behavioral tests for `EpisodicWriter.write` (`src/ingestion/writer.py`).

`write` turns one served `PushEvent` into exactly one appended
`EpisodicEntry`. It has no branches, so every hazard here is about which
value lands in which field — above all `changed_at`, which must come from
the head commit's git timestamp rather than the ingest wall-clock, or
history silently collapses into "now". The resolver's set-difference
completion semantics and the store's SQL/filtering are pinned in their own
contract suites (`tests/episodic/`) and are faked here, never re-tested.
"""

import inspect
import subprocess
from datetime import datetime, timedelta, timezone

import pytest

from src.episodic.models import EpisodicEntry
from src.ingestion.models import PushCommit
from src.ingestion.writer import EpisodicWriter
from tests.ingestion.conftest import FailingCollector, FailingEmbedder, FailingStore

# --- changed_at provenance — the silent-failure core ----------------------


async def test_changed_at_is_the_head_commits_timestamp_far_from_now(
    make_push, make_resolver, make_change, make_collector, make_writer, store, make_commit
):
    push = make_push()
    resolver = make_resolver(make_change(commits=(make_commit(),)))
    historical = datetime(2023, 3, 14, 9, 26, 53, tzinfo=timezone(timedelta(hours=2)))
    collector = make_collector({push.after: historical})
    writer = make_writer(resolver, collector)

    await writer.write(push)

    [entry] = store.entries
    assert entry.changed_at == historical
    assert abs(datetime.now(timezone.utc) - entry.changed_at) > timedelta(days=30)


async def test_changed_at_reads_push_after_not_before(
    make_push, make_resolver, make_change, make_collector, make_writer, store
):
    push = make_push()
    resolver = make_resolver(make_change())
    collector = make_collector(
        {
            push.before: datetime(2020, 1, 1, tzinfo=timezone.utc),
            push.after: datetime(2024, 6, 1, tzinfo=timezone.utc),
        }
    )
    writer = make_writer(resolver, collector)

    await writer.write(push)

    [(_, ref)] = collector.calls
    assert ref == push.after
    [entry] = store.entries
    assert entry.changed_at == datetime(2024, 6, 1, tzinfo=timezone.utc)


async def test_changed_at_preserves_tzinfo_rather_than_storing_a_naive_datetime(
    make_push, make_resolver, make_change, make_collector, make_writer, store
):
    push = make_push()
    resolver = make_resolver(make_change())
    offset = timezone(timedelta(hours=5, minutes=30))
    collector = make_collector({push.after: datetime(2022, 7, 4, 12, 0, 0, tzinfo=offset)})
    writer = make_writer(resolver, collector)

    await writer.write(push)

    [entry] = store.entries
    assert entry.changed_at.tzinfo is not None
    assert entry.changed_at.utcoffset() == timedelta(hours=5, minutes=30)


async def test_changed_at_is_derived_from_git_not_from_the_push_payload(
    make_push, make_resolver, make_change, make_collector, make_writer, mirror
):
    push = make_push()
    resolver = make_resolver(make_change())
    collector = make_collector({push.after: datetime(2021, 1, 1, tzinfo=timezone.utc)})
    writer = make_writer(resolver, collector)

    await writer.write(push)

    assert collector.calls == [(str(mirror.tree_path), push.after)]


async def test_collector_and_resolver_are_asked_against_the_same_worktree_path(
    make_push, make_resolver, make_change, make_collector, make_writer, mirror
):
    push = make_push()
    resolver = make_resolver(make_change())
    collector = make_collector({push.after: datetime(2021, 1, 1, tzinfo=timezone.utc)})
    writer = make_writer(resolver, collector)

    await writer.write(push)

    expected_path = str(mirror.tree_path)
    assert resolver.calls[0][0] == expected_path
    assert collector.calls[0][0] == expected_path


# --- entry construction / field mapping -----------------------------------


async def test_write_appends_exactly_one_entry_when_one_push_is_served(
    make_push, make_resolver, make_change, make_collector, make_writer, store, make_commit
):
    push = make_push()
    resolver = make_resolver(make_change(commits=(make_commit(),)))
    collector = make_collector({push.after: datetime(2024, 1, 1, tzinfo=timezone.utc)})
    writer = make_writer(resolver, collector)

    await writer.write(push)

    assert len(store.entries) == 1


async def test_entry_copies_repo_and_org_id_from_the_push_event(
    make_push, make_resolver, make_change, make_collector, make_writer, store, make_commit
):
    push = make_push(org_id=987654, org_login="some-org-login", repo="distinct-org/distinct-repo")
    resolver = make_resolver(make_change(repo=push.repo, commits=(make_commit(),)))
    collector = make_collector({push.after: datetime(2024, 1, 1, tzinfo=timezone.utc)})
    writer = make_writer(resolver, collector)

    await writer.write(push)

    [entry] = store.entries
    assert entry.repo == "distinct-org/distinct-repo"
    assert entry.org_id == 987654
    assert isinstance(entry.org_id, int)


async def test_commit_shas_are_set_from_the_resolved_commits_in_order(
    make_push, make_resolver, make_change, make_collector, make_writer, store, make_commit
):
    push = make_push(
        commits=(
            PushCommit(sha="zzz", message="payload message", added=(), modified=(), removed=(), author="Payload"),
        )
    )
    resolved_commits = (
        make_commit(sha="aaa", message="first"),
        make_commit(sha="bbb", message="second"),
        make_commit(sha="ccc", message="third"),
    )
    resolver = make_resolver(make_change(commits=resolved_commits))
    collector = make_collector({push.after: datetime(2024, 1, 1, tzinfo=timezone.utc)})
    writer = make_writer(resolver, collector)

    await writer.write(push)

    [entry] = store.entries
    assert entry.commit_shas == ("aaa", "bbb", "ccc")
    assert "zzz" not in entry.commit_shas


async def test_completed_tasks_are_set_verbatim_as_a_tuple_from_the_resolved_change(
    make_push, make_resolver, make_change, make_collector, make_writer, store, make_commit
):
    push = make_push()
    resolver = make_resolver(make_change(completed_tasks=("4.2.1", "4.3.2"), commits=(make_commit(),)))
    collector = make_collector({push.after: datetime(2024, 1, 1, tzinfo=timezone.utc)})
    writer = make_writer(resolver, collector)

    await writer.write(push)

    [entry] = store.entries
    assert entry.completed_tasks == ("4.2.1", "4.3.2")
    assert isinstance(entry.completed_tasks, tuple)


async def test_embedders_vector_is_stored_verbatim_as_the_entry_embedding(
    make_push, make_resolver, make_change, make_collector, make_writer, store, embedder, make_commit
):
    push = make_push()
    resolver = make_resolver(make_change(commits=(make_commit(),)))
    collector = make_collector({push.after: datetime(2024, 1, 1, tzinfo=timezone.utc)})
    embedder.vector = [0.25, -0.5, 3.0]
    writer = make_writer(resolver, collector)

    await writer.write(push)

    [entry] = store.entries
    assert entry.embedding == [0.25, -0.5, 3.0]


async def test_recorded_at_is_left_unset_so_the_store_assigns_it_server_side(
    make_push, make_resolver, make_change, make_collector, make_writer, store, make_commit
):
    push = make_push()
    resolver = make_resolver(make_change(commits=(make_commit(),)))
    collector = make_collector({push.after: datetime(2024, 1, 1, tzinfo=timezone.utc)})
    writer = make_writer(resolver, collector)

    await writer.write(push)

    [entry] = store.entries
    assert entry.recorded_at is None


# --- content composition and embedding input ------------------------------


async def test_content_joins_completed_tasks_then_commit_messages_with_newlines(
    make_push, make_resolver, make_change, make_collector, make_writer, store, make_commit
):
    push = make_push()
    resolver = make_resolver(
        make_change(
            completed_tasks=("4.2.1", "4.3.2"),
            commits=(
                make_commit(sha="aaa", message="first commit"),
                make_commit(sha="bbb", message="second commit"),
            ),
        )
    )
    collector = make_collector({push.after: datetime(2024, 1, 1, tzinfo=timezone.utc)})
    writer = make_writer(resolver, collector)

    await writer.write(push)

    [entry] = store.entries
    assert entry.content == "4.2.1\n4.3.2\nfirst commit\nsecond commit"


async def test_writer_embeds_the_resolvers_commit_messages_not_the_payload_messages(
    make_push, make_resolver, make_change, make_collector, make_writer, store, make_commit
):
    push = make_push(
        commits=(
            PushCommit(
                sha="zzz", message="PAYLOAD MESSAGE", added=(), modified=(), removed=(), author="Payload"
            ),
        )
    )
    resolver = make_resolver(make_change(commits=(make_commit(sha="aaa", message="RESOLVED MESSAGE"),)))
    collector = make_collector({push.after: datetime(2024, 1, 1, tzinfo=timezone.utc)})
    writer = make_writer(resolver, collector)

    await writer.write(push)

    [entry] = store.entries
    assert "RESOLVED MESSAGE" in entry.content
    assert "PAYLOAD MESSAGE" not in entry.content


async def test_embedder_is_called_with_the_exact_content_string_as_its_single_input(
    make_push, make_resolver, make_change, make_collector, make_writer, store, embedder, make_commit
):
    push = make_push()
    resolver = make_resolver(make_change(commits=(make_commit(),)))
    collector = make_collector({push.after: datetime(2024, 1, 1, tzinfo=timezone.utc)})
    writer = make_writer(resolver, collector)

    await writer.write(push)

    [entry] = store.entries
    assert embedder.calls == [[entry.content]]


async def test_embedder_is_called_exactly_once_regardless_of_commit_count(
    make_push, make_resolver, make_change, make_collector, make_writer, embedder, make_commit
):
    push = make_push()
    many_commits = tuple(make_commit(sha=f"sha-{i}", message=f"commit {i}") for i in range(25))
    resolver = make_resolver(make_change(commits=many_commits))
    collector = make_collector({push.after: datetime(2024, 1, 1, tzinfo=timezone.utc)})
    writer = make_writer(resolver, collector)

    await writer.write(push)

    assert len(embedder.calls) == 1


async def test_content_includes_multiline_commit_bodies_unmodified(
    make_push, make_resolver, make_change, make_collector, make_writer, store, make_commit
):
    push = make_push()
    body_message = "subject line\n\nbody paragraph one\nbody paragraph two"
    resolver = make_resolver(make_change(commits=(make_commit(sha="aaa", message=body_message),)))
    collector = make_collector({push.after: datetime(2024, 1, 1, tzinfo=timezone.utc)})
    writer = make_writer(resolver, collector)

    await writer.write(push)

    [entry] = store.entries
    assert entry.content == body_message


# --- code-only push and empty ranges ---------------------------------------


async def test_code_only_push_leaves_completed_tasks_empty_with_no_leading_newline(
    make_push, make_resolver, make_change, make_collector, make_writer, store, make_commit
):
    push = make_push()
    resolver = make_resolver(
        make_change(
            completed_tasks=(),
            commits=(
                make_commit(sha="aaa", message="fix bug"),
                make_commit(sha="bbb", message="add feature"),
            ),
        )
    )
    collector = make_collector({push.after: datetime(2024, 1, 1, tzinfo=timezone.utc)})
    writer = make_writer(resolver, collector)

    await writer.write(push)

    [entry] = store.entries
    assert entry.completed_tasks == ()
    assert entry.content == "fix bug\nadd feature"
    assert not entry.content.startswith("\n")


async def test_empty_range_produces_empty_content_and_still_appends(
    make_push, make_resolver, make_change, make_collector, make_writer, store, embedder
):
    push = make_push(before="same-sha", after="same-sha")
    resolver = make_resolver(make_change(completed_tasks=(), commits=()))
    collector = make_collector({push.after: datetime(2024, 1, 1, tzinfo=timezone.utc)})
    writer = make_writer(resolver, collector)

    await writer.write(push)

    [entry] = store.entries
    assert entry.content == ""
    assert len(store.entries) == 1
    assert embedder.calls == [[""]]


# --- append-only / no read-modify-write ------------------------------------


async def test_two_sequential_pushes_append_two_independent_entries(
    make_push, make_resolver, make_change, make_collector, make_writer, store, make_commit
):
    push_one = make_push(repo="acme/widgets-one", before="b1", after="a1")
    push_two = make_push(repo="acme/widgets-two", before="b2", after="a2")
    resolver = make_resolver(make_change(commits=(make_commit(sha="aaa", message="first"),)))
    collector = make_collector(
        {
            "a1": datetime(2024, 1, 1, tzinfo=timezone.utc),
            "a2": datetime(2024, 2, 1, tzinfo=timezone.utc),
        }
    )
    writer = make_writer(resolver, collector)

    await writer.write(push_one)
    first_entry = store.entries[0]
    await writer.write(push_two)

    assert len(store.entries) == 2
    assert store.entries[0] is first_entry
    assert store.entries[0].repo == "acme/widgets-one"
    assert store.entries[1].repo == "acme/widgets-two"


async def test_write_never_reads_or_queries_the_store(
    make_push, make_resolver, make_change, make_collector, make_writer, store, make_commit
):
    push = make_push()
    resolver = make_resolver(make_change(commits=(make_commit(),)))
    collector = make_collector({push.after: datetime(2024, 1, 1, tzinfo=timezone.utc)})
    writer = make_writer(resolver, collector)

    # `FakeStore.query`/`.recorded_commit_shas` raise if called at all, so a
    # successful write here is itself the "never reads at write time" proof.
    await writer.write(push)

    assert len(store.entries) == 1


async def test_write_does_not_derive_or_store_a_narrated_outcome(
    make_push, make_resolver, make_change, make_collector, make_writer, store, make_commit
):
    push = make_push()
    resolver = make_resolver(make_change(commits=(make_commit(),)))
    collector = make_collector({push.after: datetime(2024, 1, 1, tzinfo=timezone.utc)})
    writer = make_writer(resolver, collector)

    await writer.write(push)

    [entry] = store.entries
    assert type(entry) is EpisodicEntry

    constructor_params = inspect.signature(EpisodicWriter.__init__).parameters
    assert "reasoner" not in constructor_params
    assert "embedder" in constructor_params


# --- orchestration order and mirror self-sufficiency -----------------------


async def test_mirror_ensure_is_called_before_opening_a_worktree(
    make_push, make_resolver, make_change, make_collector, make_writer, mirror, make_commit
):
    push = make_push()
    resolver = make_resolver(make_change(commits=(make_commit(),)))
    collector = make_collector({push.after: datetime(2024, 1, 1, tzinfo=timezone.utc)})
    writer = make_writer(resolver, collector)

    await writer.write(push)

    assert mirror.events[:2] == ["ensure", "tree_enter"]


async def test_worktree_is_opened_at_push_after_with_the_pushs_repo_and_org(
    make_push, make_resolver, make_change, make_collector, make_writer, mirror, make_commit
):
    push = make_push(repo="acme/widgets", org_id=555, after="head-sha")
    resolver = make_resolver(make_change(commits=(make_commit(),)))
    collector = make_collector({push.after: datetime(2024, 1, 1, tzinfo=timezone.utc)})
    writer = make_writer(resolver, collector)

    await writer.write(push)

    assert mirror.tree_calls == [("acme/widgets", 555, "head-sha")]


async def test_resolver_is_called_with_the_worktree_path_and_pushs_before_after_range(
    make_push, make_resolver, make_change, make_collector, make_writer, mirror, make_commit
):
    push = make_push(before="range-before", after="range-after")
    resolver = make_resolver(make_change(commits=(make_commit(),)))
    collector = make_collector({push.after: datetime(2024, 1, 1, tzinfo=timezone.utc)})
    writer = make_writer(resolver, collector)

    await writer.write(push)

    assert resolver.calls == [(str(mirror.tree_path), "range-before", "range-after")]


async def test_worktree_is_closed_before_embedding_and_appending(
    make_push, make_resolver, make_change, make_collector, make_writer, mirror, make_commit
):
    push = make_push()
    resolver = make_resolver(make_change(commits=(make_commit(),)))
    collector = make_collector({push.after: datetime(2024, 1, 1, tzinfo=timezone.utc)})
    writer = make_writer(resolver, collector)

    await writer.write(push)

    tree_exit_index = mirror.events.index("tree_exit")
    embed_index = mirror.events.index("embed")
    append_index = mirror.events.index("append")
    assert tree_exit_index < embed_index < append_index


# --- error propagation (no silent history loss) ----------------------------


async def test_embedder_failure_propagates_and_appends_nothing(
    make_push, make_resolver, make_change, make_collector, make_writer, store, make_commit
):
    push = make_push()
    resolver = make_resolver(make_change(commits=(make_commit(),)))
    collector = make_collector({push.after: datetime(2024, 1, 1, tzinfo=timezone.utc)})
    failing_embedder = FailingEmbedder(RuntimeError("embed failed"))
    writer = make_writer(resolver, collector, embedder=failing_embedder)

    with pytest.raises(RuntimeError, match="embed failed"):
        await writer.write(push)

    assert store.entries == []


async def test_store_append_failure_propagates(
    make_push, make_resolver, make_change, make_collector, make_writer, make_commit
):
    push = make_push()
    resolver = make_resolver(make_change(commits=(make_commit(),)))
    collector = make_collector({push.after: datetime(2024, 1, 1, tzinfo=timezone.utc)})
    failing_store = FailingStore(RuntimeError("append failed"))
    writer = make_writer(resolver, collector, store=failing_store)

    with pytest.raises(RuntimeError, match="append failed"):
        await writer.write(push)


async def test_worktree_exits_even_when_the_resolver_raises(make_push, make_collector, make_writer, mirror):
    push = make_push()
    collector = make_collector({push.after: datetime(2024, 1, 1, tzinfo=timezone.utc)})

    class RaisingResolver:
        def resolve(self, repo_path: str, before: str, after: str):
            raise RuntimeError("resolve failed")

    writer = make_writer(RaisingResolver(), collector)

    with pytest.raises(RuntimeError, match="resolve failed"):
        await writer.write(push)

    assert "tree_exit" in mirror.events


async def test_collector_failure_propagates_without_a_datetime_now_fallback(
    make_push, make_resolver, make_change, make_writer, store, make_commit
):
    push = make_push()
    resolver = make_resolver(make_change(commits=(make_commit(),)))
    failing_collector = FailingCollector(subprocess.CalledProcessError(1, ["git"]))
    writer = make_writer(resolver, failing_collector)

    with pytest.raises(subprocess.CalledProcessError):
        await writer.write(push)

    assert store.entries == []
