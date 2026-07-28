# Plan Review: 3.3.2 — PgVectorStore (impl)

## Code Review Summary

**Files Reviewed:** plan (`16-3-3-2-pgvectorstore-impl.md`) against `src/core/config.py`, `src/core/db.py`, `src/knowledge/store.py`, `src/knowledge/schema.sql`, `tests/knowledge/conftest.py`, `tests/knowledge/test_knowledge_store_contract.py`, `tests/conftest.py`, `src/github/mirror.py`, `.env.example`, `.env.dev`, `Makefile`, and the governing spec `.ai-factory/specs/06-pgvector-knowledge-store.md`.
**Risk Level:** 🟡 Medium

### Context Gates
- **Architecture** (`.ai-factory/ARCHITECTURE.md`) — PASS. The plan reads `Settings` and feeds `create_pool(settings.postgres_dsn)` only at composition roots; `PgVectorStore` takes an injected `asyncpg.Pool` and never reads env. Knowledge feature depends on `core/` infra (`src/core/db.py` codec) — the allowed direction. No feature-to-feature coupling introduced.
- **Rules** (`.ai-factory/RULES.md`) — PASS (file is intentionally empty; no counter-defaults).
- **Roadmap** (`.ai-factory/ROADMAP.md` line 38 → spec `06-pgvector-knowledge-store.md`) — PASS. The plan is a faithful decomposition of the contract line and spec: delete-then-insert txn upsert, scoped delete, cosine-ordered optionally-repo-scoped query, DSN in `Settings`, dim-mismatch-raises guard, and the explicit "no version guard — out-of-order same-ref writes are self-healing" stance all trace directly to the spec's Change/Guards sections. File paths (`src/core/config.py`, `src/knowledge/store.py`) match the spec's `Files & types`.

Ground-truth checks that passed:
- `src/core/db.py` exists and registers the `vector` text codec via `create_pool(..., init=_init_connection)`, encoding/decoding `list[float]` ↔ pgvector text. The plan's "pass the raw `list[float]`" and its `src/core/db.py` file reference are correct (CLAUDE.md's table labels this module by its `create_pool()` function; the file is `db.py`).
- `schema.sql` uses `hnsw (embedding vector_cosine_ops)` — the plan's insistence on `<=>` (cosine distance) and its explicit warning against `<->`/`<#>` matches the index. The `test_query_orders_results_nearest_first_by_cosine` fixtures (distance 0/1/2) confirm `<=>` yields the asserted order.
- The stub `PgVectorStore` and `Chunk` value object match the plan's method bodies and hydration shape (`Chunk(content, embedding, repo, path, chunk_index)`).
- Upsert's enumerate-derived `chunk_index` correctly ignores the incoming chunks' own `repo/path/chunk_index` (all `None` from `make_chunk`) and uses the method args — matching `test_upsert_atomically_replaces_prior_chunks_for_the_path` (5→2 shrink leaves `[0, 1]`).

### Critical Issues
None that break the canonical `make test` flow.

### Issues to Address

**1. Task 1 misreads the conftest's DSN defaults, and the resulting "required" fields diverge from the established `Settings`-constructible invariant.**

Task 1 says: *"defaults only where the conftest defaults them (host/port)"* and marks `postgres_user`, `postgres_password`, `postgres_db` as **required**. That is a wrong assumption about the codebase. `tests/knowledge/conftest.py::_dsn` defaults **all five** values, not just host/port:

```python
user = os.environ.get("POSTGRES_USER", "herald_username")
password = os.environ.get("POSTGRES_PASSWORD", "herald_password")
db = os.environ.get("POSTGRES_DB", "herald_database")
```

Consequences of following the plan as written:
- Making `postgres_user/password/db` required contradicts the invariant explicitly documented in `src/github/mirror.py` (lines 30–32): *"`Settings`' defaults only keep `Settings()` constructible for the webhook test suite."* After the change, `Settings()` is no longer constructible from the webhook secret alone.
- `tests/conftest.py` monkeypatches only `GITHUB_WEBHOOK_SECRET` and `SERVE_ALLOWLIST`; it never sets `POSTGRES_*`. The webhook/ingestion suites construct `Settings()` via `get_settings()` inside the request path. Under `make test` this happens to work only because the `Makefile` does `-include .env.dev` + `export` and `.env.dev` carries `POSTGRES_*`. A bare `uv run pytest` (a supported runner per `pyproject.toml`) or a CI job without `.env.dev` exported would now fail the *webhook/ingestion* tests — suites unrelated to this task — with a pydantic `ValidationError` for missing Postgres fields.

Recommended fix: default all five fields to the conftest's own values (`postgres_user="herald_username"`, `postgres_password="herald_password"`, `postgres_db="herald_database"`, host/port as already planned). This keeps the `Settings()`-constructible invariant intact, keeps the raw-`pytest` path green, and makes the derived `postgres_dsn` produce exactly the shape `_dsn()` builds by default. If a "fail fast when unconfigured" posture is genuinely wanted for production, follow the pattern mirror.py already established — keep the field defaulted and assert presence at the composition root — rather than making the field required and coupling every `Settings()` construction to a live Postgres config. Either way, the plan's factual claim about which fields the conftest defaults must be corrected.

### Positive Notes
- The cosine-operator guidance is precise and defends against exactly the silent-failure hazard the 3.3.1 contract line called out (`<=>` vs `<->`/`<#>`, tied to `vector_cosine_ops`).
- The transaction reasoning is correct: `DELETE`+multi-row `INSERT` inside `async with conn.transaction()` gives all-or-nothing replace, and Task 3's instruction to reuse the same `DELETE` statement inside Task 2 avoids SQL duplication.
- Task 4 correctly flags the positional-parameter shift when the optional `WHERE repo = $k` clause is present and the need to build SQL/params conditionally for the `repo is None` case.
- Task 5 as a verification checkpoint (no client-side pad/truncate; rely on `vector(768)` to reject wrong dimensions) is a sound, code-free guard that matches the spec's dimension guard.
- The "no version/ordering guard" decision is explicitly grounded in the spec's self-healing rationale rather than invented.
- Dependency dependencies between tasks (Task 1 → 2/3/4; Tasks 2,4 → 5) are declared and correct.

## Deferred observations
- Affects: future composition roots / `tests/knowledge/conftest.py` — The derived `postgres_dsn` string-interpolates user/password into a URL without percent-encoding. For the current dev credentials this is fine, and matching the conftest's identical unescaped `_dsn()` shape is the correct target for this task, so it is not a defect of this plan. But a password containing URL-reserved characters (`@`, `:`, `/`, `#`) would corrupt the DSN for both `postgres_dsn` and the test `_dsn()`; whoever hardens production Postgres config should switch both to `urllib.parse.quote` or pass connection params to asyncpg individually. [routed → .ai-factory/specs/57-postgres-dsn-encoding.md]

REVIEW_PASS is intentionally NOT emitted: Issue 1 is a finding within this task's file boundary (`src/core/config.py`) and must be resolved.
