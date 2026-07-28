# Code Review: 7.1.1 — Reasoner contract + retrieval invariants (red tests)

**Scope reviewed:** `git diff HEAD` / `git status` — new code files only:
`src/reasoning/__init__.py`, `src/reasoning/reasoner.py`, `tests/reasoning/__init__.py`,
`tests/reasoning/conftest.py`, `tests/reasoning/test_reasoner_contract.py`. (The
`.ai-factory/` plan/plan-review/json artifacts are process files, not reviewed for runtime behavior.)

**Task type:** red-tests deliverable — the `answer` method is intentionally a stub that raises
`NotImplementedError`; the tests must be red *only* because of that stub, and 7.1.2 must be able to
turn them green unchanged.

## Verification performed

- **Ran the suite** (`uv run pytest tests/reasoning/`): all 7 tests fail, every one at
  `src/reasoning/reasoner.py:56` `raise NotImplementedError` — none fail from an import, fixture,
  signature, or collection error. This is the exact red-for-the-right-reason contract the spec's
  Guards and Verification sections require.
- **Suite-wide collection** (`uv run pytest --collect-only`): 85 tests collected, no errors — the
  new `reasoning` package and its conftest do not break collection elsewhere.
- **Collaborator APIs checked against ground truth:**
  - `FakeEmbedder.embed(texts) -> list[list[float]]` matches `Embedder` (`src/llm/embedder.py`).
  - `FakeKnowledgeStore` implements `upsert`/`delete`/`query` — the full `KnowledgeStore` ABC
    (`src/knowledge/store.py`); `query(embedding, k, repo=None)` signature matches.
  - `FakeEpisodicStore` implements `append`/`query`/`recorded_commit_shas` — the full
    `EpisodicStore` ABC (`src/episodic/store.py`); `query(..., since=None, until=None)` matches, and
    the fake records `since`/`until` so a future test could assert the no-time-window invariant.
  - `FakeLLMClient.generate(prompt) -> str` matches `LLMClient` (`src/llm/client.py`).
  - `Chunk` (from `src/knowledge/store.py`) and `EpisodicEntry` (from `src/episodic/models.py`,
    fields `repo/org_id/completed_tasks/commit_shas/content/embedding/changed_at`) are constructed
    correctly by the `make_chunk`/`make_entry` builders.
- **`asyncio_mode = "auto"`** (`pyproject.toml:22`) confirmed — async test functions need no
  decorator, matching the code as written.

## Correctness against the four invariants

- **One embedding, two stores** — `FakeEmbedder` returns the *same list object* every call, so
  `test_answer_embeds_once...` can assert `embed` was called exactly once, both stores received
  `SENTINEL_VECTOR` by value, and `knowledge_embedding is episodic_embedding` by identity. This
  correctly pins "embed once and reuse," and the natural `embed([query])[0]` implementation will
  satisfy the identity check.
- **`repo`-scoping** — two tests pin bare `repo="api"` → both stores, and `repo=None` → both stores.
  Correct, and format-free.
- **Honest no-memory** — the control-case design correctly accepts *either* spec-permitted
  resolution (short-circuit before `generate`, or a distinct no-memory prompt marker) without
  coupling to prompt text. Sound.
- **Failure isolation** — knowledge-raises, episodic-raises, and both-raise cases each assert
  `answer` returns a `str` rather than propagating. This pins the primary silent-failure surface
  (no exception escapes).

## Findings

### Minor (non-blocking) — failure-isolation tests under-pin the "degrade to the survivor" half of invariant #4

`test_knowledge_failure_is_isolated_from_episodic_survivor` and its symmetric twin
(`tests/reasoning/test_reasoner_contract.py:75-94`) assert only `isinstance(result, str)`. That pins
"the raise is caught, never propagated" — but it does **not** distinguish "grounded in the surviving
store's results" from "silently degraded to the no-memory path." An implementation that catches the
store exception and then *discards* the survivor's results (falling through to no-memory framing)
would still pass these two tests, even though the spec's invariant #4 says `answer` returns a string
*"built from the surviving store's results."*

This is a genuine coverage gap, but it is **minor and partly inherent**: the plan's Phase-2 note and
the spec explicitly forbid asserting on the combined-context/prompt format, and there is no fully
resolution-agnostic way to prove "the survivor's content reached the prompt" without touching that
format (under the no-memory "Resolution B", even asserting `fake_llm.calls` is non-empty would not
distinguish the two paths). The authors' choice to stop at `isinstance str` is defensible within
those constraints. No change is required for the red-tests deliverable to be correct; noting it so
7.1.2 (or a follow-up) is aware the "survivor is actually used" property is asserted only in prose,
not in a test.

## Summary

No bugs, no security issues, no correctness defects. No migrations involved (the queried stores own
their own `schema.sql`; this task adds none). The stub-and-mocks design is clean, the tests are red
strictly because of the stub, they will green under a correct 7.1.2 implementation, and they avoid
encoding the open choices (`k`, prompt text, context format) the spec reserves for 7.1.2. The single
finding above is a non-blocking, partly-inherent coverage note on the failure-isolation tests.
