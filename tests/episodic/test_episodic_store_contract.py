from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from src.episodic.models import EpisodicEntry
from src.episodic.store import EpisodicStore, PgEpisodicStore

EMBEDDING_DIM = 768


def _unit_vector(axis: int, value: float = 1.0) -> list[float]:
    vector = [0.0] * EMBEDDING_DIM
    vector[axis] = value
    return vector


async def test_query_orders_results_nearest_first_by_cosine(
    store: PgEpisodicStore, make_entry: Callable[..., EpisodicEntry]
) -> None:
    nearest = make_entry("nearest", axis=0, value=1.0)  # same direction as query -> distance 0
    middle = make_entry("middle", axis=1, value=1.0)  # orthogonal to query -> distance 1
    farthest = make_entry("farthest", axis=0, value=-1.0)  # opposite of query -> distance 2

    await store.append(nearest)
    await store.append(middle)
    await store.append(farthest)

    results = await store.query(_unit_vector(axis=0), k=3)

    assert results[0].content == "nearest"
    assert results[1].content == "middle"
    assert results[2].content == "farthest"


async def test_since_until_filter_on_changed_at_not_recorded_at(
    store: PgEpisodicStore, make_entry: Callable[..., EpisodicEntry]
) -> None:
    now = datetime.now(timezone.utc)
    recent_since = now - timedelta(days=1)
    t0 = now - timedelta(days=60)
    t1 = now - timedelta(days=50)

    # Must-not-leak-in: old changed_at, fresh recorded_at (append server-assigns
    # recorded_at = now()). A filter mistakenly built on recorded_at would let
    # this leak into the "recent" window below.
    misleading_old_changed = make_entry(
        "misleading-old-changed-fresh-recorded",
        axis=0,
        changed_at=now - timedelta(days=365),
    )
    # In-window control for the recent query, so its result set isn't
    # trivially empty.
    in_recent_window = make_entry(
        "in-recent-window", axis=0, changed_at=now - timedelta(hours=1)
    )
    # Must-not-leak-out: changed_at inside the historical window [t0, t1],
    # but recorded_at (~now) falls outside it. A filter mistakenly built on
    # recorded_at would drop this even though changed_at is in range.
    misleading_historical = make_entry(
        "misleading-historical-in-window-changed-fresh-recorded",
        axis=0,
        changed_at=t0 + timedelta(days=5),
    )
    # Out-of-window control for both queries above.
    outside_both_windows = make_entry(
        "outside-both-windows", axis=0, changed_at=now - timedelta(days=10)
    )

    await store.append(misleading_old_changed)
    await store.append(in_recent_window)
    await store.append(misleading_historical)
    await store.append(outside_both_windows)

    recent_results = await store.query(_unit_vector(axis=0), k=10, since=recent_since)
    recent_contents = {entry.content for entry in recent_results}
    assert "in-recent-window" in recent_contents
    assert "misleading-old-changed-fresh-recorded" not in recent_contents
    assert "outside-both-windows" not in recent_contents

    historical_results = await store.query(
        _unit_vector(axis=0), k=10, since=t0, until=t1
    )
    historical_contents = {entry.content for entry in historical_results}
    assert "misleading-historical-in-window-changed-fresh-recorded" in historical_contents
    assert "outside-both-windows" not in historical_contents
    assert "in-recent-window" not in historical_contents


def test_episodic_store_is_structurally_append_only() -> None:
    assert not hasattr(EpisodicStore, "update")
    assert not hasattr(EpisodicStore, "delete")
    assert not hasattr(EpisodicStore, "upsert")
    assert not hasattr(PgEpisodicStore, "update")
    assert not hasattr(PgEpisodicStore, "delete")
    assert not hasattr(PgEpisodicStore, "upsert")
