## Code Review Summary

**Task:** 4.1.1 — Episodic store contract + schema (red tests)
**Files reviewed (read in full):** `src/episodic/__init__.py`, `src/episodic/models.py`, `src/episodic/store.py`, `src/episodic/schema.sql`, `tests/episodic/__init__.py`, `tests/episodic/conftest.py`, `tests/episodic/test_episodic_store_contract.py`. Verified against the plan, the governing spec (`.ai-factory/specs/44-episodic-store-contract.md`), and the mirrored ground-truth code (`src/knowledge/store.py`, `src/knowledge/schema.sql`, `src/core/db.py`, `tests/knowledge/*`).
**Risk Level:** 🟢 Low — a contract/red-test task with no production logic; the code is correct against spec and matches the proven knowledge-store shapes.

### What was verified

- **`EpisodicEntry` (models.py):** Frozen dataclass with all spec'd fields and correct types (`completed_tasks`/`commit_shas` as `tuple[str, ...]`, `changed_at: datetime`, `recorded_at: datetime | None = None`). Field ordering is valid — the sole defaulted field (`recorded_at`) is last. Model is pure (no Postgres, no I/O). The `list[float]` embedding on a frozen dataclass mirrors `Chunk` exactly; entries are never hashed (tests key sets on `.content` strings), so the unhashable-list concern does not arise.
- **`EpisodicStore` ABC + `PgEpisodicStore` stub (store.py):** Exactly two abstract methods — `append` and `query(embedding, k, repo, since, until)`. **No `update`/`delete`/`upsert` exists**, so append-only is structural, not a runtime check. Signatures name no Postgres concept (docstrings mention commit/`changed_at` semantics, not pgvector). Stub `__init__(pool)` mirrors `PgVectorStore`; both bodies `raise NotImplementedError`, so the behavioral tests are genuinely red and 4.1.2 greens them by filling the bodies.
- **`schema.sql`:** Idempotent (`CREATE EXTENSION/TABLE/INDEX IF NOT EXISTS`), applies cleanly alongside `chunks` on the same DB. `embedding vector(768)` matches the `chunks` column and 3.2's embedder. hnsw `vector_cosine_ops` ANN index + `(repo, changed_at)` btree present. `recorded_at timestamptz NOT NULL DEFAULT now()` correctly makes the ingest time server-assigned — the premise the windowing test depends on.
- **Fixtures (conftest.py):** `pg_pool` applies the episodic schema then `TRUNCATE episodic_entries`, matching the knowledge fixture. `make_entry` defaults `changed_at` to a tz-aware value (`datetime(2024, 1, 1, tzinfo=timezone.utc)`) and the windowing test builds every boundary from `datetime.now(timezone.utc)` — the plan-review-1 timezone footgun is fully addressed (no naive `timestamptz` encode, no aware-vs-naive comparison `TypeError`).
- **Tests:** `asyncio_mode = "auto"` (pyproject) lets the un-decorated async tests run. Cosine-order test asserts exact nearest→middle→farthest order (distances 0/1/2), so a reversed `ORDER BY` cannot pass. The windowing test is adversarial in both directions and — traced against the planted timestamps — a filter mistakenly built on `recorded_at` fails both queries (query 1 would wrongly include the old-changed/fresh-recorded entry; query 2 would wrongly empty the historical result set). All planted timestamps use day-scale gaps with no entry near a window edge, so no host UTC offset can flip an assertion. The structural test asserts absence of mutation methods on both the ABC and the stub — green-by-shape, as the plan honestly notes.

### Findings

None. The code is faithful to the spec and to the mirrored knowledge-store contract; the behavioral tests are correctly red against the raising stub, the schema is valid and idempotent, and the timezone handling flagged in plan-review-1 is correctly implemented.

REVIEW_PASS
