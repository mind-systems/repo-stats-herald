import asyncio

from src.ingestion.served_repos import ServedRepoStore

ORG_A = 111
ORG_B = 222


def _for_org(pairs: list[tuple[int, str]], org_id: int) -> list[str]:
    return sorted(repo for oid, repo in pairs if oid == org_id)


# --- Task 1: add() behavior ------------------------------------------------


async def test_add_records_every_pair_when_given_a_fresh_list_of_repos(
    served_store: ServedRepoStore,
) -> None:
    await served_store.add(ORG_A, ["a", "b", "c"])

    assert set(await served_store.all()) == {(ORG_A, "a"), (ORG_A, "b"), (ORG_A, "c")}


async def test_add_leaves_the_set_unchanged_when_the_same_repos_are_added_a_second_time(
    served_store: ServedRepoStore,
) -> None:
    await served_store.add(ORG_A, ["a", "b"])

    await served_store.add(ORG_A, ["a", "b"])  # re-delivered installation_repositories

    assert set(await served_store.all()) == {(ORG_A, "a"), (ORG_A, "b")}


async def test_add_inserts_only_the_new_repos_when_the_batch_partially_overlaps(
    served_store: ServedRepoStore,
) -> None:
    await served_store.add(ORG_A, ["a", "b"])

    await served_store.add(ORG_A, ["b", "c"])

    assert set(await served_store.all()) == {(ORG_A, "a"), (ORG_A, "b"), (ORG_A, "c")}


async def test_add_records_the_pair_once_when_the_same_repo_appears_twice_in_a_batch(
    served_store: ServedRepoStore,
) -> None:
    await served_store.add(ORG_A, ["a", "a"])

    assert await served_store.all() == [(ORG_A, "a")]


async def test_add_keeps_both_rows_when_two_different_orgs_add_the_same_repo_name(
    served_store: ServedRepoStore,
) -> None:
    await served_store.add(ORG_A, ["shared"])
    await served_store.add(ORG_B, ["shared"])

    assert set(await served_store.all()) == {(ORG_A, "shared"), (ORG_B, "shared")}


async def test_add_stores_a_large_org_id_losslessly_when_it_exceeds_32_bits(
    served_store: ServedRepoStore,
) -> None:
    big_org_id = 2**32 + 7

    await served_store.add(big_org_id, ["repo"])

    assert await served_store.all() == [(big_org_id, "repo")]


# --- Task 2: add() guards and iterable contract -----------------------------


async def test_add_is_a_noop_when_the_repos_iterable_is_empty(
    served_store: ServedRepoStore,
) -> None:
    await served_store.add(ORG_A, [])

    assert await served_store.all() == []


async def test_add_consumes_a_one_shot_generator_correctly(
    served_store: ServedRepoStore,
) -> None:
    def repos():
        yield "a"
        yield "b"

    await served_store.add(ORG_A, repos())

    assert set(await served_store.all()) == {(ORG_A, "a"), (ORG_A, "b")}


# --- Task 3: remove() org isolation and scoping -----------------------------


async def test_remove_leaves_another_orgs_identically_named_repo_intact(
    served_store: ServedRepoStore,
) -> None:
    await served_store.add(ORG_A, ["shared"])
    await served_store.add(ORG_B, ["shared"])

    await served_store.remove(ORG_A, ["shared"])

    assert await served_store.all() == [(ORG_B, "shared")]


async def test_remove_deletes_only_the_named_repos_when_others_exist_for_the_same_org(
    served_store: ServedRepoStore,
) -> None:
    await served_store.add(ORG_A, ["a", "b", "c"])

    await served_store.remove(ORG_A, ["b"])

    assert set(await served_store.all()) == {(ORG_A, "a"), (ORG_A, "c")}


async def test_remove_deletes_the_intersection_when_the_batch_mixes_present_and_absent(
    served_store: ServedRepoStore,
) -> None:
    await served_store.add(ORG_A, ["a", "b"])

    await served_store.remove(ORG_A, ["b", "z"])

    assert await served_store.all() == [(ORG_A, "a")]


async def test_remove_removes_nothing_when_the_repo_is_not_in_the_set_for_that_org(
    served_store: ServedRepoStore,
) -> None:
    await served_store.add(ORG_A, ["a"])

    await served_store.remove(ORG_A, ["not-there"])

    assert await served_store.all() == [(ORG_A, "a")]


async def test_remove_leaves_the_orgs_other_repos_intact_when_draining_it_to_empty(
    served_store: ServedRepoStore,
) -> None:
    await served_store.add(ORG_A, ["a", "b"])
    await served_store.add(ORG_B, ["c"])

    await served_store.remove(ORG_A, ["a", "b"])

    assert await served_store.all() == [(ORG_B, "c")]


# --- Task 4: remove() guards and iterable contract --------------------------


async def test_remove_is_a_noop_when_the_repos_iterable_is_empty(
    served_store: ServedRepoStore,
) -> None:
    await served_store.add(ORG_B, ["c"])  # second org survives an install-create no-op

    await served_store.remove(ORG_A, [])

    assert await served_store.all() == [(ORG_B, "c")]


async def test_remove_accepts_a_generator_when_repos_is_not_a_list(
    served_store: ServedRepoStore,
) -> None:
    await served_store.add(ORG_A, ["a", "b"])

    def repos():
        yield "a"

    await served_store.remove(ORG_A, repos())

    assert await served_store.all() == [(ORG_A, "b")]


# --- Task 5: all() return contract ------------------------------------------


async def test_all_returns_an_empty_list_when_the_table_is_empty(
    served_store: ServedRepoStore,
) -> None:
    assert await served_store.all() == []


async def test_all_returns_org_id_repo_tuples_in_that_exact_positional_order(
    served_store: ServedRepoStore,
) -> None:
    await served_store.add(ORG_A, ["a"])

    pairs = await served_store.all()

    org_id, repo = pairs[0]
    assert isinstance(org_id, int)
    assert isinstance(repo, str)


async def test_all_returns_2_tuples_not_asyncpg_record_objects(
    served_store: ServedRepoStore,
) -> None:
    await served_store.add(ORG_A, ["a"])

    pairs = await served_store.all()

    assert type(pairs[0]) is tuple


async def test_all_orders_by_org_id_then_repo_when_rows_are_inserted_out_of_order(
    served_store: ServedRepoStore,
) -> None:
    await served_store.add(ORG_B, ["z"])
    await served_store.add(ORG_A, ["b"])
    await served_store.add(ORG_A, ["a"])

    assert await served_store.all() == [(ORG_A, "a"), (ORG_A, "b"), (ORG_B, "z")]


async def test_all_returns_every_orgs_pairs_when_multiple_orgs_are_served(
    served_store: ServedRepoStore,
) -> None:
    await served_store.add(ORG_A, ["a"])
    await served_store.add(ORG_B, ["b"])

    assert set(await served_store.all()) == {(ORG_A, "a"), (ORG_B, "b")}


# --- Task 6: convergence under replayed events ------------------------------


async def test_add_and_remove_converge_to_the_same_set_regardless_of_order(
    served_store: ServedRepoStore,
) -> None:
    # forward: add(a) then remove(b) — b was never present
    await served_store.add(ORG_A, ["a"])
    await served_store.remove(ORG_A, ["b"])
    forward = _for_org(await served_store.all(), ORG_A)

    # reverse: remove(b) then add(a) — same operations, opposite order, isolated org
    await served_store.remove(ORG_B, ["b"])
    await served_store.add(ORG_B, ["a"])
    reverse = _for_org(await served_store.all(), ORG_B)

    assert forward == ["a"]
    assert reverse == ["a"]


async def test_add_and_remove_of_the_same_repo_yield_the_ordering_specific_result(
    served_store: ServedRepoStore,
) -> None:
    # add then remove the same repo — ends up absent
    await served_store.add(ORG_A, ["x"])
    await served_store.remove(ORG_A, ["x"])
    add_then_remove = _for_org(await served_store.all(), ORG_A)

    # remove then add the same repo — ends up present, since remove of an absent row is a no-op
    await served_store.remove(ORG_B, ["x"])
    await served_store.add(ORG_B, ["x"])
    remove_then_add = _for_org(await served_store.all(), ORG_B)

    assert add_then_remove == []
    assert remove_then_add == ["x"]


async def test_add_reaches_the_seeded_state_when_an_installation_create_seed_is_replayed(
    served_store: ServedRepoStore,
) -> None:
    await served_store.add(ORG_A, ["a"])
    await served_store.add(ORG_A, ["b"])

    # installation-create redelivered with the org's authoritative full repo list
    await served_store.add(ORG_A, ["a", "b", "c"])

    assert _for_org(await served_store.all(), ORG_A) == ["a", "b", "c"]


async def test_concurrent_adds_for_one_org_apply_without_error(
    served_store: ServedRepoStore,
) -> None:
    await asyncio.gather(
        served_store.add(ORG_A, ["a"]),
        served_store.add(ORG_A, ["b"]),
        served_store.add(ORG_A, ["a"]),
    )

    assert _for_org(await served_store.all(), ORG_A) == ["a", "b"]
