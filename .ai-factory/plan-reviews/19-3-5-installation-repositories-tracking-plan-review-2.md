## Plan Review — 3.5 Installation-repositories tracking (round 2)

**Plan:** `.ai-factory/plans/19-3-5-installation-repositories-tracking.md`
**Files Reviewed (targets + reference chain):** plan, `src/ingestion/router.py`, `src/ingestion/models.py`, `src/main.py`, `src/core/db.py`, `src/core/config.py`, `src/knowledge/store.py`, `src/knowledge/schema.sql`, `tests/knowledge/conftest.py`, `tests/ingestion/test_webhook_contract.py`, `docs/spec/ingestion.md`, `.ai-factory/specs/36-installation-repositories-tracking.md`, `.ai-factory/ROADMAP.md` (line 3.5, 10.2), `.ai-factory/ARCHITECTURE.md`, `.ai-factory/RULES.md`, prior review `…-plan-review-1.md`
**Risk Level:** 🟢 Low

### Context Gates
- **Architecture (`ARCHITECTURE.md`)** — OK. Every load-bearing principle is honored: `ServedRepoStore` receives an injected `asyncpg.Pool` (DI), concretes are wired only in `src/main.py`'s lifespan (composition root), SQL is encapsulated inside the store class, and the no-ABC decision is correctly justified against principle 4 (line 84: "Introduce an ABC when a real second implementation is imminent — not speculatively"). The store lives inside the `ingestion` feature package, consistent with feature ownership.
- **Rules (`RULES.md`)** — OK. File is intentionally empty (no counter-defaults); nothing to check.
- **Roadmap (`ROADMAP.md` 3.5 + spec `36-…`)** — OK, faithful. Contract line and spec both call for a `served_repos` table on 3.3's `create_pool`, HMAC-verified receipt (2.1), allowlist gating (2.2), `INSERT … ON CONFLICT DO NOTHING` on added / `DELETE` on removed / seed the full list on `installation` create, idempotent + order-free, "maintains the set only." Each maps to a task. The `served_repos` `(org_id, repo)` shape matches the downstream 10.2 consumer's expectation ("iterate `served_repos`, carries `org_id`"); 3.6 backfill left untouched, as specified.

### Round-1 finding — resolved
Review-1's single issue was that the earlier plan's "leave the push path completely untouched" wording was a control-flow trap: an implementer keeping the early `if X-GitHub-Event != "push": return 204` (router.py:60‑61) would have every installation event swallowed before reaching the new branch. **This is now fixed.** Task 4 restructures around the trap explicitly ("this is the crux, and the trap"), names router.py:60‑61 as the line that "must not survive as-is," prescribes the correct per-event dispatch (read `event_name` once → push branch returns its `JSONResponse` verbatim → installation branch → generic `204` tail), and clarifies that "push pipeline unaffected" means the push *behavior* is byte-for-byte identical, not that the dispatch structure is frozen. The correction is precise and grounded.

### Grounding verification (re-checked against code)
- **Org identity `installation.account.id`** — matches `docs/spec/ingestion.md` line 38 (`organization.id` / `installation.account.id` are the same org identity). Push reads `payload["organization"]["id"]` (router.py:42) into the same `frozenset[int]` allowlist namespace (config.py:19), so `installation.account.id` gates correctly. ✅
- **Short repo name, not `full_name`** — matches `_parse_push_event` (`payload["repository"]["name"]`, router.py:44). `r["name"]` yields the short name for `repositories_added`/`repositories_removed`/`repositories`. ✅
- **`bigint` for `org_id` + composite PK** — mirrors `knowledge/schema.sql`'s idempotent `CREATE TABLE IF NOT EXISTS` + PK idiom; the PK is what makes the upsert idempotent. ✅
- **`create_pool(settings.postgres_dsn)`** — signatures match: `create_pool(dsn: str)` (db.py:22) and `Settings.postgres_dsn` property (config.py:37‑42). ✅
- **Schema-load-relative-to-file** — `tests/knowledge/conftest.py:11` uses `Path(__file__).resolve()…`; the plan's Task 5 "resolve the path relative to this file" is the same idiom (`src/main.py` → `ingestion/schema.sql`). ✅
- **Store shape** — `ServedRepoStore.__init__(self, pool)` mirrors `PgVectorStore.__init__` (store.py:46); `executemany` for the seed/add and set-based `DELETE … = ANY($2::text[])` for remove are both idempotent and order-free, satisfying the spec's "concurrent/replayed events need no ordering" guard structurally. ✅
- **Dual-array parse for `installation_repositories`** — reading both `repositories_added` and `repositories_removed` (each `.get(…, [])`) regardless of the `added`/`removed` action is correct and robust: the inactive array is simply absent → `[]` → a no-op, so no action switch is needed. ✅
- **Lifespan / test coexistence** — confirmed: `test_webhook_contract.py` drives only push/ping and never the installation branch, and `TestClient(app)` used without a `with` block means lifespan (hence `app.state.served_repo_store`) never runs — push tests keep passing without Postgres. The allowlist gate returning `204` before touching the store means even an unlisted-org installation request would not need the store. ✅

### Critical Issues
None. Migration is added (Task 1), API usage is correct, security posture is preserved (HMAC stays first, allowlist gates `204` before any DB write — matching push discipline), and no architectural rule is violated.

### Positive Notes
- The **Pinned decisions** block remains exemplary and now the round-1 gap is closed inside Task 4 itself rather than only in prose — the trap is called out at the exact line number it lives on.
- Idempotency is designed structurally (composite PK + `ON CONFLICT DO NOTHING` + set-based `DELETE`), so the order-free guarantee holds by construction, not by runtime coordination.
- Scope discipline is clean: "maintains the set only," no backfill, no speculative purge-on-delete, no speculative ABC — each refusal is grounded in a cited spec clause or architecture principle.

## Deferred observations
- Affects: infra / future Phase-3 wiring (3.6) — `src/core/db.py`'s `create_pool` unconditionally calls `set_type_codec("vector", schema="public", …)` on every connection, which resolves the `vector` type's OID at connect time. The lifespan Task 5 adds applies only `src/ingestion/schema.sql` (which does **not** `CREATE EXTENSION vector`), so the pool startup silently depends on the pgvector extension already existing in `herald_database`. On any correctly provisioned machine this holds — the extension is a documented one-time prerequisite in the project `CLAUDE.md` setup and reusing the shared `create_pool` is the spec-mandated choice ("3.3's asyncpg pool") — so this is not a defect in this task's boundary. It is worth making the extension dependency explicit when 3.6 wires the knowledge store into the same app root (that path needs `chunks` and the extension applied at startup), rather than continuing to rely on manual setup. [dismissed]

PLAN_REVIEW_PASS
