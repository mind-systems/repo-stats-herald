"""Red tests pinning `Reasoner.answer`'s silent-failure retrieval invariants
against the stub.

Every test below calls `answer` as if it were already implemented and
asserts on the outcome; each fails only because the stub raises
`NotImplementedError` — never because of an import, fixture, or signature
mismatch. 7.1.2's real implementation turns these green unchanged; none of
them assert on `k`'s value, exact prompt text, or combined-context format,
since the spec leaves those open.
"""


async def test_answer_embeds_once_and_shares_embedding_with_both_stores(
    reasoner, fake_embedder, fake_knowledge, fake_episodic
):
    await reasoner.answer("what changed in api last week?")

    assert len(fake_embedder.calls) == 1
    assert fake_embedder.calls[0] == ["what changed in api last week?"]

    assert len(fake_knowledge.calls) == 1
    assert len(fake_episodic.calls) == 1

    knowledge_embedding = fake_knowledge.calls[0][0]
    episodic_embedding = fake_episodic.calls[0][0]

    assert knowledge_embedding == fake_embedder.SENTINEL_VECTOR
    assert episodic_embedding == fake_embedder.SENTINEL_VECTOR
    assert knowledge_embedding is episodic_embedding


async def test_repo_scoping_passes_bare_repo_to_both_stores(reasoner, fake_knowledge, fake_episodic):
    await reasoner.answer("what changed?", repo="api")

    assert fake_knowledge.calls[0][2] == "api"
    assert fake_episodic.calls[0][2] == "api"


async def test_no_repo_scoping_passes_none_to_both_stores(reasoner, fake_knowledge, fake_episodic):
    await reasoner.answer("what changed across the org?")

    assert fake_knowledge.calls[0][2] is None
    assert fake_episodic.calls[0][2] is None


async def test_honest_no_memory_is_distinguishable_from_grounded_path(
    reasoner, fake_knowledge, fake_episodic, fake_llm, make_chunk
):
    # No-memory case: both stores return nothing.
    fake_knowledge.result = []
    fake_episodic.result = []

    await reasoner.answer("what changed?")

    no_memory_generate_calls = list(fake_llm.calls)

    # Control case: the knowledge store has something to ground the answer in.
    fake_knowledge.result = [make_chunk()]
    fake_llm.calls.clear()

    await reasoner.answer("what changed?")

    grounded_generate_calls = list(fake_llm.calls)

    if not no_memory_generate_calls:
        # Resolution A: no memory short-circuits before any LLM call, while
        # the grounded control case does call `generate`.
        assert grounded_generate_calls
    else:
        # Resolution B: both call `generate`, but the no-memory prompt
        # carries an explicit marker a grounded prompt does not.
        assert no_memory_generate_calls != grounded_generate_calls


async def test_knowledge_failure_is_isolated_from_episodic_survivor(
    reasoner, fake_knowledge, fake_episodic, fake_llm, make_entry
):
    # Baseline: genuine no-memory, both stores empty (no failure involved).
    fake_knowledge.result = []
    fake_episodic.result = []
    await reasoner.answer("what changed?")
    no_memory_calls = list(fake_llm.calls)

    # Knowledge raises, episodic survives with real content.
    fake_llm.calls.clear()
    fake_knowledge.error = RuntimeError("knowledge store unavailable")
    fake_episodic.result = [make_entry()]

    result = await reasoner.answer("what changed?")
    survivor_calls = list(fake_llm.calls)

    assert isinstance(result, str)
    if not no_memory_calls:
        # Resolution A: no-memory short-circuits before `generate`; a real
        # survivor must still reach it — discarding the survivor down to
        # the short-circuit would leave `survivor_calls` empty too.
        assert survivor_calls
    else:
        # Resolution B: the survivor-grounded prompt must differ from the
        # explicit no-memory marker prompt — a discarded survivor would
        # otherwise produce the identical no-memory prompt.
        assert survivor_calls != no_memory_calls


async def test_episodic_failure_is_isolated_from_knowledge_survivor(
    reasoner, fake_knowledge, fake_episodic, fake_llm, make_chunk
):
    # Baseline: genuine no-memory, both stores empty (no failure involved).
    fake_knowledge.result = []
    fake_episodic.result = []
    await reasoner.answer("what changed?")
    no_memory_calls = list(fake_llm.calls)

    # Episodic raises, knowledge survives with real content.
    fake_llm.calls.clear()
    fake_episodic.error = RuntimeError("episodic store unavailable")
    fake_knowledge.result = [make_chunk()]

    result = await reasoner.answer("what changed?")
    survivor_calls = list(fake_llm.calls)

    assert isinstance(result, str)
    if not no_memory_calls:
        # Resolution A: no-memory short-circuits before `generate`; a real
        # survivor must still reach it — discarding the survivor down to
        # the short-circuit would leave `survivor_calls` empty too.
        assert survivor_calls
    else:
        # Resolution B: the survivor-grounded prompt must differ from the
        # explicit no-memory marker prompt — a discarded survivor would
        # otherwise produce the identical no-memory prompt.
        assert survivor_calls != no_memory_calls


async def test_both_stores_failing_falls_back_to_no_memory_path(
    reasoner, fake_knowledge, fake_episodic, fake_llm
):
    # Baseline: genuine no-memory, both stores empty (no failure involved).
    fake_knowledge.result = []
    fake_episodic.result = []
    await reasoner.answer("what changed?")
    no_memory_calls = list(fake_llm.calls)

    # Both stores raise.
    fake_llm.calls.clear()
    fake_knowledge.error = RuntimeError("knowledge store unavailable")
    fake_episodic.error = RuntimeError("episodic store unavailable")

    result = await reasoner.answer("what changed?")
    both_raise_calls = list(fake_llm.calls)

    assert isinstance(result, str)
    # Both stores raising must take the same honest no-memory path as both
    # returning empty — not some other, unmarked failure prompt.
    assert both_raise_calls == no_memory_calls
