# Review: 6.1.1 — Project graph contract + schema (red tests)

## Scope
Reviewed all new files in the staged changeset:
- `src/graph/__init__.py`, `src/graph/models.py`, `src/graph/schema.sql`, `src/graph/store.py`
- `tests/graph/__init__.py`, `tests/graph/conftest.py`, `tests/graph/test_project_graph_contract.py`

Cross-checked against the plan, `.ai-factory/specs/47-project-graph-contract.md`, and the existing `src/knowledge/` + `src/episodic/` modules the diff mirrors.

## Correctness verification

- **Red for the right reason.** Every test's first `await store.<method>(...)` hits a stub that `raise NotImplementedError`, so all four tests fail on missing logic — exactly the red-test contract (spec Guards / Verification). No test can pass spuriously: each calls `add_edge` before any assertion.
- **Async collection.** `pyproject.toml` sets `asyncio_mode = "auto"`, so the bare `async def test_*` functions (no `@pytest.mark.asyncio`) are collected and run — matches `tests/episodic/test_episodic_store_contract.py`. `testpaths=["tests"]`, `pythonpath=["."]`, and the `tests/graph/__init__.py` make the package importable and discoverable.
- **Schema is genuinely exercised.** The `pg_pool` fixture executes `schema.sql` and then `TRUNCATE project_edges`; the TRUNCATE would fail if the DDL didn't create the table, so "schema applies cleanly on the shared pool" (spec Verification) is covered by fixture setup even though the stub never writes.
- **PK deliberately excludes `source`.** `PRIMARY KEY (from_repo, to_repo, kind)` preserves the collision hazard the tests exist to pin — correctly *not* "fixed" by widening the key (spec Change / Guards).
- **pgvector codec is safe here.** `create_pool` registers a `public.vector` type codec on every connection. `project_edges` has no vector column and `schema.sql` correctly omits `CREATE EXTENSION vector`, but the codec registration still succeeds because pgvector is a per-database, per-machine prerequisite already installed by the knowledge/episodic setup — the type OID resolves regardless of this table. No missing-extension breakage introduced.
- **Contract shapes match the eventual impl.** `Edge` is a frozen DTO mirroring `Chunk`/`EpisodicEntry`; `EdgeKind(StrEnum)` values map directly to the `kind text` column; `PgProjectGraph(pool)` matches `PgEpisodicStore(pool)`. Tests assert only observable outputs (returned `Edge`s, neighbor lists), so 6.1.2 can green them without test edits. Directed-neighbor semantics (`neighbors("a") == ["b"]`, `neighbors("b") == []`, then `b→a` makes `a` a neighbor of `b`) are encoded correctly.

## Observation (non-blocking, not a defect in this diff)
Like the existing `tests/episodic` and `tests/knowledge` contract suites, these tests require a live Postgres (`herald_database` with pgvector) — the `pg_pool` fixture connects at setup. If Postgres is absent, the tests go red at fixture setup rather than at `NotImplementedError`. This is the established repo-wide convention for DB-backed contract tests, not something this changeset introduces, so no change is warranted.

## Result
No correctness, security, or runtime findings. The changeset is a faithful, minimal red-tests stub consistent with the plan and the surrounding code.

REVIEW_PASS
