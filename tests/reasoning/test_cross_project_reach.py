"""Tests for 7.2's cross-project reach: repo-scoped answers fold in semantic
context from related neighbor projects — discovered via org-wide retrieval
unioned with the directed project graph — inside `_gather_context`."""

_NEIGHBOR_SECTION_MARKER = "relates to / unblocks"


async def test_neighbor_surfaced_via_graph_is_queried_and_reaches_prompt(
    reasoner, fake_knowledge, fake_graph, fake_llm, make_chunk
):
    primary = make_chunk(repo="api", content="primary content")
    neighbor = make_chunk(repo="worker", content="worker content")
    fake_knowledge.results = {"api": [primary], None: [], "worker": [neighbor]}
    fake_graph.result = ["worker"]

    result = await reasoner.answer("what changed?", repo="api")

    neighbor_calls = [call for call in fake_knowledge.calls if call[2] == "worker"]
    assert len(neighbor_calls) == 1

    prompt = fake_llm.calls[-1]
    assert _NEIGHBOR_SECTION_MARKER in prompt
    assert "worker content" in prompt
    assert isinstance(result, str)


async def test_neighbor_surfaced_via_retrieval_is_queried_and_reaches_prompt(
    reasoner, fake_knowledge, fake_graph, fake_llm, make_chunk
):
    primary = make_chunk(repo="api", content="primary content")
    retrieval_hit = make_chunk(repo="worker", content="retrieval-surfaced marker")
    neighbor_chunk = make_chunk(repo="worker", content="worker content")
    fake_knowledge.results = {"api": [primary], None: [retrieval_hit], "worker": [neighbor_chunk]}
    fake_graph.result = []

    await reasoner.answer("what changed?", repo="api")

    neighbor_calls = [call for call in fake_knowledge.calls if call[2] == "worker"]
    assert len(neighbor_calls) == 1
    assert "worker content" in fake_llm.calls[-1]


async def test_neighbor_from_both_discovery_paths_is_folded_once_with_bare_id(
    reasoner, fake_knowledge, fake_graph, fake_llm, make_chunk
):
    primary = make_chunk(repo="api", content="primary content")
    retrieval_hit = make_chunk(repo="worker", content="retrieval-surfaced marker")
    neighbor_chunk = make_chunk(repo="worker", content="worker content")
    fake_knowledge.results = {"api": [primary], None: [retrieval_hit], "worker": [neighbor_chunk]}
    fake_graph.result = ["worker"]

    await reasoner.answer("what changed?", repo="api")

    neighbor_calls = [call for call in fake_knowledge.calls if call[2] == "worker"]
    assert len(neighbor_calls) == 1

    for call in fake_knowledge.calls:
        repo_arg = call[2]
        assert repo_arg is None or "/" not in repo_arg
    for repo_arg in fake_graph.calls:
        assert "/" not in repo_arg


async def test_single_embed_call_despite_neighbor_fan_out(
    reasoner, fake_embedder, fake_knowledge, fake_graph, make_chunk
):
    fake_knowledge.results = {
        "api": [make_chunk(repo="api")],
        None: [],
        "worker": [make_chunk(repo="worker")],
        "billing": [make_chunk(repo="billing")],
    }
    fake_graph.result = ["worker", "billing"]

    await reasoner.answer("what changed?", repo="api")

    assert len(fake_embedder.calls) == 1


async def test_one_failing_neighbor_is_dropped_without_losing_primary_or_other_neighbors(
    reasoner, fake_knowledge, fake_graph, fake_llm, make_chunk
):
    primary = make_chunk(repo="api", content="primary content")
    good_neighbor = make_chunk(repo="worker", content="worker content")
    fake_knowledge.results = {"api": [primary], None: [], "worker": [good_neighbor]}
    fake_knowledge.errors = {"broken": RuntimeError("neighbor store unavailable")}
    fake_graph.result = ["broken", "worker"]

    result = await reasoner.answer("what changed?", repo="api")

    assert isinstance(result, str)
    prompt = fake_llm.calls[-1]
    assert "primary content" in prompt
    assert "worker content" in prompt

    attempted_repos = {call[2] for call in fake_knowledge.calls}
    assert "broken" in attempted_repos
    assert "worker" in attempted_repos


async def test_no_repo_scope_skips_neighbor_folding_entirely(
    reasoner, fake_knowledge, fake_graph, make_chunk
):
    fake_knowledge.result = [make_chunk(repo="api")]

    await reasoner.answer("what changed across the org?")

    assert len(fake_knowledge.calls) == 1
    assert fake_graph.calls == []


async def test_no_neighbors_found_leaves_single_project_answer_unchanged(
    reasoner, fake_knowledge, fake_graph, fake_llm, make_chunk
):
    primary = make_chunk(repo="api", content="primary content")
    fake_knowledge.results = {"api": [primary], None: []}
    fake_graph.result = []

    await reasoner.answer("what changed?", repo="api")

    prompt = fake_llm.calls[-1]
    assert _NEIGHBOR_SECTION_MARKER not in prompt
    neighbor_calls = [call for call in fake_knowledge.calls if call[2] not in ("api", None)]
    assert neighbor_calls == []
