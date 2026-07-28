## Plan Review Summary

**Plan:** `.ai-factory/plans/67-servedrepostore.md` — Test plan for `ServedRepoStore`
**Governing spec:** `.ai-factory/specs/76-served-repo-store-test-plan.md` (roadmap entry `ROADMAP_TESTS.md` §ServedRepoStore)
**Risk Level:** 🔴 High — one blocking assumption that breaks an existing suite if implemented literally.

### Context Gates
- **Architecture** (`ARCHITECTURE.md`): OK. The plan adds test-only files, reuses the settled real-Postgres contract-test pattern (`create_pool` from `src.core.db`, per-suite `schema.sql` + `TRUNCATE`), and does not cross any module boundary. No dependency-direction violation.
- **Rules** (`RULES.md`): OK. No test/fixture/conftest conventions defined; nothing to violate.
- **Roadmap** (`ROADMAP_TESTS.md` §ServedRepoStore, Spec 76): Aligned in scope — idempotent add, org-scoped removal, `all` ordering, empty-iterable guards, replay convergence, second org populated in every removal case, router branch out of scope. The plan faithfully mirrors the spec's case list. **WARN:** the plan (and the spec) both rest on a codebase claim that is now false — see Critical Issue 1.

### Critical Issues

**1. `tests/ingestion/conftest.py` already exists — the plan's "new file" + `store` fixture collides with the live episodic-writer suite.**

The plan's Fixtures section says: *"Fixtures (new file: `tests/ingestion/conftest.py`)"* and defines a `store` fixture returning `ServedRepoStore(pg_pool)`. The governing spec repeats this: *"`tests/ingestion/` currently has no `conftest.py`."* That was true when the spec was authored, but ground truth has since changed — the file exists (284 lines, created during the episodic-writer test task) and **already defines a `store` fixture**:

```python
# tests/ingestion/conftest.py:186
@pytest.fixture
def store(events: list[str]) -> FakeStore:
    return FakeStore(events)
```

`tests/ingestion/test_episodic_writer.py` depends on that `store` fixture pervasively (`store.entries`, ~12 test functions). If the implementer follows the plan literally they will either:
- **create/overwrite** a "new" `conftest.py`, destroying the FakeMirror/FakeStore/`make_writer` fixtures and breaking the entire episodic-writer suite; or
- **append** a second `@pytest.fixture def store` to the existing file, which rebinds the name in module scope — `test_episodic_writer.py` then receives a `ServedRepoStore` and every `store.entries` access raises `AttributeError`.

Either path is a green-to-red regression outside this task's intended surface.

Note the plan *does* guard against shadowing — but it guards the wrong set: *"must not redefine root fixture names (`client`/`sign`/`push_payload`/`TEST_ORG_ID`)"*. Those live in `tests/conftest.py` and were never at risk. The actual collision is with the **local** ingestion-conftest fixtures (`store`, and potentially `events`/`mirror`/`embedder`/`make_*`).

**Required fix:**
- Treat `tests/ingestion/conftest.py` as an **existing file to extend**, not a new file. Add `_dsn()`, `SCHEMA_PATH`, `pg_pool`, and the store fixture to it (or place the Postgres fixtures directly in `test_served_repos.py`).
- Do **not** name the Postgres-backed fixture `store`. Rename it (e.g. `served_store`) and update every case in Task 1–6 to request the renamed fixture. `pg_pool` is safe to add (no existing definition).
- Reconcile the stale claim in Spec 76 §Instantiation / §Gotchas ("currently has no conftest") — the code wins; the spec line is out of date.

### Non-blocking Issues

**2. The bigint case may not actually exercise > 32 bits.** Task 1's *"should store a large org_id losslessly when the org id exceeds 32 bits"* suggests *"use `TEST_ORG_ID` or a value above 2^31"*. `TEST_ORG_ID = 244165546` is ~2.4×10⁸ — below 2³¹ (2147483648) — so it fits a 32-bit `int` and would pass even against a mistaken `integer` column, making the test title false. Pin this case to a value strictly above 2³¹ (e.g. `2**32 + 7`) so it genuinely proves the `bigint` column. (Inherited from the spec; still in-scope to correct here.)

### Positive Notes
- Case coverage is thorough and each case names the exact code construct it pins (composite PK, `ON CONFLICT DO NOTHING`, `org_id = $1` scoping, `list(repos)` normalization, `ORDER BY`, tuple-not-Record mapping). The highest-value cross-tenant `remove` isolation test is correctly foregrounded.
- The "populate a second org in every `remove` case" discipline is stated up front and matches the spec's silent-failure gotcha exactly.
- The order-dependence nuance in Task 6 is right: convergent for different repos, deliberately *non*-convergent (assert each ordering) for the same repo. This matches the spec and the real semantics of `add`/`remove`.
- Reusing `tests/graph/conftest.py`'s `_dsn`/`pg_pool`/`TRUNCATE-at-setup` shape is the correct, settled pattern; the `create_pool` vector-codec dependency is already satisfied on the test DB by the sibling suites.
- Router installation branch is correctly scoped out, matching the roadmap guard.

Fix Critical Issue 1 (and ideally Issue 2) and the plan is sound.
