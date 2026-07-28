## Code Review Summary

**Files Reviewed:** Plan `15-3-3-1-knowledgestore-contract-schema-red-tests.md` (6 tasks) against the codebase and its reference chain (ROADMAP line 3.3.1 → spec `42-knowledge-store-contract.md` → `docs/spec/understanding.md`; sibling impl spec `06-pgvector-knowledge-store.md`).
**Risk Level:** 🟢 Low

### Context Gates
- **Architecture (`.ai-factory/ARCHITECTURE.md`):** PASS. The plan honors every dependency rule. `src/core/db.py` is placed as cross-cutting infra (like `config.py`), the sole holder of Postgres/pgvector knowledge; features depend on the `KnowledgeStore` abstraction. `Chunk` + `KnowledgeStore` live inside the owning `src/knowledge/` package. The pool factory takes a primitive `dsn` and is wired at the composition root — concretes are not constructed inside feature/service classes. The ABC-per-boundary shape mirrors `src/llm/client.py` / `embedder.py` exactly.
- **Rules (`.ai-factory/RULES.md`):** PASS. File is intentionally empty (no project counter-defaults); nothing to violate.
- **Roadmap (`.ai-factory/ROADMAP.md` line 3.3.1):** PASS. The plan implements the contract line faithfully: `src/core/db.py` asyncpg pool, `chunks` schema with `(repo,path,chunk_index)` PK, `embedding vector(768)`, ANN cosine index, `KnowledgeStore` ABC (`upsert`/`delete`/`query`, names no pgvector concept), and three adversarial red tests. The 3.3.1/3.3.2 seam is respected: stub raises, `Settings.postgres_*`+DSN deferred to 3.3.2 (line 38 / spec 06), `db.py` written once here.
- **Governing spec (`42-knowledge-store-contract.md`):** PASS. All three pinned invariants (true cosine-nearest order with an explicit adversarial planted-farthest assertion, atomic per-`(repo,path)` replace with no leftover `chunk_index`, path-scoped delete) map one-to-one to Task 6. `<dim>` is correctly resolved to `768` for `nomic-embed-text` (`Settings.embed_model`, `config.py:13`).

### Critical Issues
None. The plan is internally consistent, technically sound, and grounded in the actual codebase:
- The `set_type_codec("vector", schema="public", ..., format="text")` approach is the correct asyncpg idiom for pgvector without pulling in the `pgvector`/`numpy` packages, and it justifies why the ABC can traffic in plain `list[float]`.
- Dataclass field ordering is valid (required `content`/`embedding` before the defaulted `repo`/`path`/`chunk_index`).
- `asyncio_mode = "auto"` + `pytest-asyncio` in the `dev` group is the right call: existing sync tests (`TestClient`-based) are unaffected, and async fixtures/tests need no per-test marker. Adding it to `[tool.pytest.ini_options]` while keeping `testpaths`/`pythonpath` is correct.
- Test layout (`tests/knowledge/__init__.py` + `conftest.py`) matches the established per-package convention (`tests/github/`, `tests/ingestion/`), and the root `tests/conftest.py` fixtures do not collide.
- The DSN default in the fixture matches the dev DB documented in `CLAUDE.md`, and `POSTGRES_*` already exist in `.env.example` — reading env directly here (not via `Settings`) correctly defers the `Settings` change to 3.3.2 per spec 06.
- Tests are red for the right reason: `PgVectorStore`'s methods raise `NotImplementedError`, not an import/fixture error, so 3.3.2 greens them unchanged.

### Positive Notes
- The cosine-order test is specified adversarially (planted farthest vector, explicit index-position assertions) — exactly what catches a reversed `ORDER BY`, which is the silent-failure hazard the whole task exists to guard.
- Deterministic, hand-computable fixed 768-dim unit-vector embeddings make the cosine assertions robust rather than flaky.
- The atomic-replace test verifies the *replace* (5→2 chunks, indices `0,1`, no leftover `2..4`) rather than merely the PK-forbidden duplicate — it targets the real invariant, and the plan explicitly calls out that distinction.
- Clean 3.3.1/3.3.2 seam: stable class name + constructor (`PgVectorStore(pool)`) so tests move red→green with zero edits; `db.py` and `schema.sql` written complete now.

## Deferred observations
- Affects: dev-machine provisioning (documented prerequisite, outside this task's file boundary) — In Task 5 the `pg_pool` fixture calls `create_pool(dsn)` *before* applying `schema.sql`. `asyncpg.create_pool()` opens `min_size` connections eagerly on `await`, so each connection's `init` callback runs `set_type_codec("vector", ...)` at pool-creation time, which requires the `vector` type (and thus the extension) to already exist in the catalog. This holds on any machine that followed `CLAUDE.md`'s first-time setup (`CREATE EXTENSION IF NOT EXISTS vector` on `herald_database`), so the tests pass as intended and the spec's verification ("schema applies cleanly against a dev pgvector") is met. The only failure mode is a fresh DB missing the manual extension step, where pool creation would fail with a less obvious error than "run the setup" — the schema.sql's own `CREATE EXTENSION` runs too late to cover the codec on such a DB. A one-line hardening (register the codec lazily/tolerantly, or apply the extension on a raw connection before pool init) would remove the ordering dependency, but is not required for this task under its documented environment. [dismissed]

PLAN_REVIEW_PASS
