# Plan Review: 3.3.2 — PgVectorStore (impl) — round 2

## Code Review Summary

**Files Reviewed:** plan (`16-3-3-2-pgvectorstore-impl.md`) against `src/core/config.py`, `src/core/db.py`, `src/knowledge/store.py`, `src/knowledge/schema.sql`, `tests/knowledge/conftest.py`, `tests/knowledge/test_knowledge_store_contract.py`, `tests/conftest.py`, `src/github/mirror.py`, `.env.example`, `.env.dev`, the governing spec `.ai-factory/specs/06-pgvector-knowledge-store.md`, and the prior review (`...-plan-review-1.md`).
**Risk Level:** 🟢 Low

### Context Gates
- **Architecture** (`.ai-factory/ARCHITECTURE.md`) — PASS. `PgVectorStore` receives an injected `asyncpg.Pool` and never reads env; `Settings`/`create_pool(settings.postgres_dsn)` are wired only at composition roots. The knowledge feature depends on `core/` infra (`src/core/db.py` codec) — the allowed direction. No feature-to-feature coupling.
- **Rules** (`.ai-factory/RULES.md`) — PASS (file is intentionally empty; no counter-defaults to enforce).
- **Roadmap** (`.ai-factory/ROADMAP.md` → spec `06-pgvector-knowledge-store.md`) — PASS. The plan is a faithful decomposition of the spec's Change/Guards/Verification: txn delete-then-insert upsert, scoped delete, cosine-ordered optionally-repo-scoped query, DSN in `Settings`, dim-mismatch-raises guard, and the "no version guard — self-healing" stance all trace directly to the spec. File paths (`src/core/config.py`, `src/knowledge/store.py`) match the spec's `Files & types`.

### Round-1 finding — resolved
Plan-review-1's sole finding (Task 1 misread the conftest as defaulting only host/port, and marked `user/password/db` as **required**, which would have broken the documented `Settings()`-constructible invariant) is fully addressed in this revision:
- Task 1 now reads *"Default all five fields to the same values `tests/knowledge/conftest.py::_dsn` defaults them to — the conftest defaults every value, not just host/port,"* and lists all five with the exact conftest defaults (`herald_username` / `herald_password` / `herald_database`, `localhost`, `5432`).
- It explicitly states *"All five must stay defaulted (not required)"* and grounds the rationale in `src/github/mirror.py` lines 30–32 and `tests/conftest.py`'s monkeypatch scope.
- Verified against ground truth: the corrected claim matches `tests/knowledge/conftest.py::_dsn` (lines 16–22, all five values defaulted) and the invariant in `src/github/mirror.py` (lines 30–32).

### Ground-truth checks that passed
- `src/core/db.py` registers the `vector` text codec via `create_pool(..., init=_init_connection)`, marshalling `list[float]` ↔ pgvector text. The plan's "pass the raw `list[float]`" and its `src/core/db.py` reference are correct (CLAUDE.md's table labels the module by its `create_pool()` function; the file is `db.py`).
- `schema.sql` uses `hnsw (embedding vector_cosine_ops)` on `vector(768)` — the plan's insistence on `<=>` and its explicit warning against `<->`/`<#>` matches the index. The `test_query_orders_results_nearest_first_by_cosine` fixtures (distance 0/1/2 for same/orthogonal/opposite) confirm `<=>` yields the asserted nearest-first order.
- Upsert's `enumerate`-derived `chunk_index` correctly ignores the incoming chunks' own `repo/path/chunk_index` (all `None` from `make_chunk`) and uses the method args — matching `test_upsert_atomically_replaces_prior_chunks_for_the_path` (5→2 shrink leaves `[0, 1]`, no stale higher indices).
- No `.env` file exists (only `.env.dev`, which is not the configured `env_file=".env"`), so a bare `uv run pytest` constructs `Settings()` from defaults — the all-defaulted Postgres fields keep the webhook/ingestion suites green, and `postgres_dsn` yields exactly the shape `_dsn()` builds by default. `.env.example`'s empty `POSTGRES_*` values are not loaded (no `.env`), so no interference.
- The stub `PgVectorStore` and `Chunk` value object match the plan's method bodies and hydration shape (`Chunk(content, embedding, repo, path, chunk_index)`).
- Task dependencies (Task 1 → 2/3/4; Tasks 2,4 → 5) are declared and correct.

### Critical Issues
None.

### Positive Notes
- The cosine-operator guidance is precise and defends against exactly the silent-failure hazard the 3.3.1 contract called out (`<=>` vs `<->`/`<#>`, tied to `vector_cosine_ops`).
- The transaction reasoning is sound: `DELETE` + multi-row `INSERT` inside `async with conn.transaction()` gives all-or-nothing replace; Task 3's instruction to reuse the same `DELETE` statement inside Task 2 avoids SQL duplication.
- Task 4 correctly flags the positional-parameter shift when the optional `WHERE repo = $k` clause is present and the need to build SQL/params conditionally for `repo is None`.
- Task 5 as a code-free verification checkpoint (no client-side pad/truncate; rely on `vector(768)` to reject wrong dimensions) matches the spec's dimension guard.
- The "no version/ordering guard" decision is explicitly grounded in the spec's self-healing rationale rather than invented.

## Deferred observations
- Affects: future composition roots / `tests/knowledge/conftest.py` — The derived `postgres_dsn` string-interpolates user/password into a URL without percent-encoding. For the current dev credentials this is fine, and matching the conftest's identical unescaped `_dsn()` shape is the correct target for this task. But a password containing URL-reserved characters (`@`, `:`, `/`, `#`) would corrupt the DSN for both `postgres_dsn` and the test `_dsn()`; whoever hardens production Postgres config should switch both to `urllib.parse.quote` or pass connection params to asyncpg individually. The plan already scopes this out explicitly, so it is not a defect of this plan. [routed → .ai-factory/specs/57-postgres-dsn-encoding.md]

PLAN_REVIEW_PASS
