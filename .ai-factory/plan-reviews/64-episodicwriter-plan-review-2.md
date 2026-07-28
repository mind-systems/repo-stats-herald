## Plan Review Summary

**Plan:** `.ai-factory/plans/64-episodicwriter.md` — Test Plan: EpisodicWriter
**Files Reviewed:** plan + spec 72 + 7 source/config files verified against ground truth
**Risk Level:** 🟢 Low

### Context Gates
- **Architecture** (`.ai-factory/ARCHITECTURE.md`): PASS — no boundary/dependency concern. This is a test-only plan touching `tests/ingestion/` and a new `tests/ingestion/conftest.py`; the plan explicitly fakes the lower layers (`LinkedChangeResolver`, `PgEpisodicStore`) rather than reaching across feature internals, consistent with the feature-modular pattern.
- **Rules** (`.ai-factory/RULES.md`): PASS — file carries no counter-defaults; nothing to enforce.
- **Roadmap** (`.ai-factory/ROADMAP_TESTS.md:14`): PASS — the plan links to the correct governing spec `.ai-factory/specs/72-episodic-writer-test-plan.md`, and the plan's tasks cover exactly the hazards that entry names (timestamp provenance, field mapping, embedded text, code-only push, single-append, never-reads-at-write-time). The plan's `64-` prefix is the orchestrator task counter, not roadmap task 64 — no mislinkage.

### Critical Issues
None.

### Verification against ground truth

Every codebase assumption in the plan was checked against the actual source and holds:

- **Constructor order** `EpisodicWriter(mirror, resolver, embedder, store, collector)` — matches `src/ingestion/writer.py:24-36` and the wiring at `src/main.py:99`. The plan's emphasis that collector is last (after store) is accurate and the footgun warning is well-placed.
- **`mirror.tree(repo, org_id, ref)`** is a synchronous `@contextlib.contextmanager` yielding a `Path` (`src/github/mirror.py:133-163`) — the plan's sync-CM FakeMirror and the "sync today, awaitable after 20.2.2" note are correct; 20.2.2 is indeed still `[ ]` in `ROADMAP.md:163`.
- **`resolver.resolve(str(tree), before, after)`** — writer passes `str(tree)` (`writer.py:42`); the plan's assertion that the resolver receives a string, not the `Path` and not the `"org/repo"` name, is grounded.
- **`collector.commit_timestamp(str(tree), push.after)`** with `check=True` — `collector.py:293-300` raises `CalledProcessError` on failure, so Task 7's "collector raises `subprocess.CalledProcessError`, writer does not fall back to `datetime.now()`" case is exercisable and the writer indeed has no fallback.
- **`content = "\n".join([*change.completed_tasks, *(c.message for c in change.commits.commits)])`** (`writer.py:45`) — confirms tasks-first ordering, newline separator, no leading newline in the code-only case, and `""` for the empty range. Task 3/4 assertions match exactly.
- **`[embedding] = await self._embedder.embed([content])`** (`writer.py:46`) — one-element batched call; the 25-commit `len(embedder.calls) == 1` assertion is meaningful.
- **`EpisodicEntry`** fields and `recorded_at: datetime | None = None` default (`src/episodic/models.py`) — Task 2's `recorded_at is None` and `org_id` int-not-string assertions are valid; writer never sets `recorded_at`.
- **`EpisodicStore`** has exactly three abstract methods `append` / `query` / `recorded_commit_shas` (`src/episodic/store.py`) — the FakeStore-must-implement-all-three and query/recorded raising as the "never reads at write time" double-duty is correct.
- **`Embedder`** ABC `async embed(texts) -> list[list[float]]` (`src/llm/embedder.py`) — subclassable fake is valid.
- **`PushEvent`** carries `org_id: int`, `repo`, `before`, `after`, `commits: tuple[PushCommit, ...]`; `PushCommit` has `sha`/`message` (`src/ingestion/models.py`) — the "make payload messages/SHAs differ from resolved commits" fixture is buildable and the source-mix-up assertions are decidable.
- **`asyncio_mode = "auto"`** and `pytest-asyncio` present (`pyproject.toml:17,22`); `tests/ingestion/` has `__init__.py` but no existing `conftest.py` or `test_episodic_writer.py` — the plan's "build a new conftest" instruction is correct and non-colliding.

### Positive Notes
- The plan correctly isolates the one silent-failure hazard (git timestamp vs. ingest wall-clock) and pins it with the far-from-now gap assertion rather than bare equality — the single most important test in the suite, and it would not survive a `datetime.now()` swap.
- Scope boundaries are drawn precisely: set-difference completion, cosine ordering, and commit-log parsing are delegated to their existing contract suites, avoiding coupling this suite to git/Postgres fixtures it does not need.
- Error-propagation cases correctly exploit the writer's straight-line structure (resolver/collector inside the `with`, embed/append after it) to assert both propagation and worktree-exit ordering.
- Fakes use real frozen dataclasses rather than `Mock`, so field-name typos surface — a deliberate and correct choice for catch-the-mapping tests.

PLAN_REVIEW_PASS
