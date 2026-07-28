## Code Review Summary

**Files Reviewed:** 1 plan (`64-episodicwriter.md`) verified against `src/ingestion/writer.py` and its whole dependency chain (`src/episodic/models.py`, `linked_change.py`, `store.py`, `src/commits/models.py`, `collector.py`, `src/ingestion/models.py`, `src/llm/embedder.py`, `src/github/mirror.py`, `src/main.py`, `pyproject.toml`) plus spec `72-episodic-writer-test-plan.md`.
**Risk Level:** 🟢 Low

### Context Gates
- **Architecture** — PASS. This is a test-only plan; it writes `tests/ingestion/test_episodic_writer.py` + a new `tests/ingestion/conftest.py` and touches no production module, so it introduces no boundary or dependency violation. The fakes correctly subclass the real seams (`Embedder`, `EpisodicStore`) and use real frozen dataclasses (`LinkedChange`, `Commit`, `CommitContext`, `PushEvent`).
- **Rules** — PASS. `.ai-factory/RULES.md` is intentionally empty (no counter-defaults); nothing to violate.
- **Roadmap** — PASS. Linkage is sound: the plan targets spec `.ai-factory/specs/72-episodic-writer-test-plan.md`, which is the exact `Spec:` named by the **EpisodicWriter** task in `.ai-factory/ROADMAP_TESTS.md` (line 14). The `64` in the plan filename is the plan sequence number, not spec 64 (an unrelated missing-reference task); no confusion in the plan body. The governing production task (`ROADMAP.md` 4.3) confirms the hazard the plan centers on — `changed_at` from the head commit, append-only, write-time-cheap.

### Critical Issues
None. Every assumption the plan makes about the codebase was verified against ground truth:

- Constructor order `EpisodicWriter(mirror, resolver, embedder, store, collector)` — matches `writer.py:24-31` **and** `src/main.py:99`. The plan's repeated warning about the footgun order is accurate.
- `content = "\n".join([*change.completed_tasks, *(c.message for c in change.commits.commits)])` (`writer.py:45`) — the plan's "tasks first, then resolved commit messages, no leading newline when tasks empty" is exactly right, including the empty-range `content == ""` with no early-return guard.
- `[embedding] = await self._embedder.embed([content])` (`writer.py:46`) — single one-element batch; `embedder.calls == [[content]]` and the 25-commit `len(calls) == 1` assertion are correct. `FakeEmbedder` returning `[[0.1]*768]` destructures cleanly, including for the `[""]` empty case.
- `changed_at = self._collector.commit_timestamp(str(tree), push.after)` (`writer.py:43`) — provenance is `push.after` against the yielded worktree path (a `str`, not the `Path`, not `"org/repo"`); `commit_timestamp` uses `check=True` (`collector.py:298`) so a failure raises `subprocess.CalledProcessError` and there is no `datetime.now()` fallback — Task 7's last case is verifiable exactly as written.
- `commit_timestamp` uses `%cI` + `datetime.fromisoformat` → always tz-aware (`collector.py:293-300`); the plan's aware-vs-naive gotcha and the "far from now" gap assertion are correct, and `EpisodicEntry.changed_at` is `timestamptz`-bound with `recorded_at` defaulting to `None` (`models.py:14`), so "leave `recorded_at` unset" holds.
- `EpisodicStore` has exactly the three abstract methods (`append`, `query`, `recorded_commit_shas`) the `FakeStore` must implement (`store.py:9-36`); the two-raise "never reads at write time" doubling is valid since `write` only calls `append`.
- `RepoMirror.tree` is a synchronous `@contextlib.contextmanager` (`mirror.py:133-134`) and `ensure` is sync (`mirror.py:108`); the "sync CM used with plain `with`" fake shape is correct, and the `finally` (`mirror.py:159-163`) guarantees `tree_exit` runs on resolver/collector exceptions — Task 6/7 ordering assertions hold.
- `asyncio_mode = "auto"` confirmed (`pyproject.toml:22`); `tests/ingestion/` exists with `__init__.py` and **no** `conftest.py` today, so the plan's "new `tests/ingestion/conftest.py`" is accurate.
- `PushEvent` carries both `org_id: int` and `org_login: str` (`models.py:15-22`), so Task 2's "assert `org_id` stays an `int`, never the `org_login` string" is a decidable, non-trivial check.

### Issue to address (minor)
- **Task 5, case `should not derive or store any narrated outcome field when writing` (plan line 80; mirrors spec line 68).** The wording "the constructor takes no `Reasoner`/**LLM client**" is imprecise against ground truth: the real constructor *does* take an LLM-adjacent dependency — `embedder: Embedder` (`writer.py:29`), the embedding seam. A test that literally asserts "no LLM client in the signature" would contradict the actual constructor and either fail or be written brittly. The genuine invariant is "no `Reasoner` (no narration/outcome derivation at write time)". Recommend narrowing the case to assert the absence of a `Reasoner` specifically (and that the appended object is exactly an `EpisodicEntry`), leaving the `embedder` dependency untouched. This is a phrasing fix within the test file's boundary, so it is a finding rather than a deferred observation.

### Positive Notes
- The plan is unusually well-grounded: it names the exact silent-failure hazard (wall-clock `changed_at` collapsing history to "now"), then designs the fixtures to make that failure *decidable* — deliberately divergent payload-vs-resolved messages/SHAs, a `dict[ref -> datetime]` collector so a `push.before` read returns a different timestamp, and a "far from now" gap assertion rather than bare equality.
- Scope boundaries are drawn correctly: set-difference completion semantics, cosine ordering, and commit-log parsing are explicitly deferred to their existing contract suites (`tests/episodic/`, `tests/commits/`), which do own those behaviors — no redundant coupling to git/Postgres fixtures.
- Forward-compatibility is handled honestly: the sync-mirror-today / awaitable-later (roadmap 20.2.2 / spec 61) note tells the implementer to keep behavioral assertions surviving the async migration.
- Error-propagation coverage (Task 7) closes the loop on the hazard — no partial entry, no `datetime.now()` fallback, worktree still exited on resolver failure.

---

The plan is architecturally sound and its codebase assumptions are fully verified; the single minor phrasing fix above (Task 5's "LLM client" → "Reasoner") is the only change needed before implementation.
