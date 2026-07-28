# Code Re-Review: 7.1.1 — Reasoner contract + retrieval invariants (red tests)

Re-review after fixes for `review-1.md`. Files re-read fresh via Read (session memory not trusted):
`src/reasoning/reasoner.py`, `tests/reasoning/conftest.py`, `tests/reasoning/test_reasoner_contract.py`.

## Verdict on previous finding

### Minor (review-1): failure-isolation tests under-pin the "degrade to the survivor" half of invariant #4 — **Fixed**

Review-1 flagged that `test_knowledge_failure_is_isolated_from_episodic_survivor` and its twin
asserted only `isinstance(result, str)`, so an implementation that caught the store exception but
*discarded* the survivor's results (silently degrading to no-memory) would still pass.

The three failure-isolation tests were rewritten to add a genuine no-memory baseline and a
resolution-agnostic comparison against it. Current content of the cited region
(`tests/reasoning/test_reasoner_contract.py:75-102`):

```python
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
```

This now pins the survivor half without coupling to prompt/context format: under Resolution A
(short-circuit) it asserts the survivor still reached `generate`; under Resolution B it asserts the
survivor-grounded prompt differs from the no-memory prompt. An implementation that discards the
survivor down to the no-memory path fails in both branches. The episodic-survivor twin
(`test_reasoner_contract.py:105-132`) applies the identical pattern with the roles swapped, and
`test_both_stores_failing_falls_back_to_no_memory_path` (`:135-155`) now asserts
`both_raise_calls == no_memory_calls`, pinning that both-raise takes the *same* honest no-memory path
as both-empty rather than some unmarked failure prompt — matching the spec's degrade-don't-crash
guard.

**Evidence it stays a valid red test / greens under a correct 7.1.2:** the comparisons are
resolution-agnostic and consistent with the spec (survivor → grounded path distinct from no-memory;
both-raise → identical to no-memory), so a spec-conforming implementation passes without
over-specification. Confirmed still red for the right reason below.

## Full re-review for new issues

- **Ran `uv run pytest tests/reasoning/`:** all 7 tests fail at `src/reasoning/reasoner.py:56`
  `raise NotImplementedError` — none fail from import, fixture, signature, or collection errors. The
  new `fake_llm` fixture dependency added to the three failure tests resolves correctly (defined in
  `conftest.py:96-98`). Red-for-the-right-reason contract holds.
- **Ran `uv run pytest --collect-only`:** 85 tests collected, no errors — the package still does not
  break suite-wide collection.
- **`reasoner.py` unchanged and correct:** `answer` remains a pure stub raising `NotImplementedError`
  (`:56`); the class imports only abstractions (`LLMClient`/`Embedder`/`KnowledgeStore`/
  `EpisodicStore`) and constructs no concretes — DI/architecture guards intact.
- **`conftest.py` unchanged:** fakes still implement the full ABCs (`KnowledgeStore`:
  `upsert`/`delete`/`query`; `EpisodicStore`: `append`/`query`/`recorded_commit_shas`;
  `Embedder.embed`; `LLMClient.generate`), all signatures matching ground truth. The
  same-object `SENTINEL_VECTOR` still backs the identity assertion in the embed-once test.
- No migrations (queried stores own their own `schema.sql`; this task adds none), no security surface
  (mocks only, no network/DB), no type mismatches, no race conditions.

No new issues.

REVIEW_PASS
