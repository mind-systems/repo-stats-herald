## Plan Review Summary

**Plan:** `.ai-factory/plans/67-servedrepostore.md` — Test plan for `ServedRepoStore`
**Governing spec:** `.ai-factory/specs/76-served-repo-store-test-plan.md` (roadmap entry `ROADMAP_TESTS.md` §ServedRepoStore)
**Files Reviewed:** plan + `src/ingestion/served_repos.py`, `src/ingestion/schema.sql`, `src/ingestion/router.py`, `tests/ingestion/conftest.py`, `tests/graph/conftest.py`, `tests/conftest.py`
**Risk Level:** 🟢 Low — the revision closes both prior-round blockers; every ground-truth claim now verified.

### Context Gates
- **Architecture** (`ARCHITECTURE.md`): OK. Test-only additions; reuses the settled real-Postgres contract-test shape (`create_pool` from `src.core.db`, per-suite `schema.sql` + `TRUNCATE`). No module boundary crossed, no dependency-direction violation.
- **Rules** (`RULES.md`): OK. No test/fixture/conftest conventions defined; nothing to violate.
- **Roadmap** (`ROADMAP_TESTS.md` §ServedRepoStore, Spec 76): Aligned in scope — idempotent add, org-scoped removal, `all` ordering, empty-iterable guards, replay convergence, second org populated in every removal case, router branch out of scope. The revised plan mirrors the spec's case list faithfully and now overrides the spec's stale "no conftest" ground-truth claim, as the code requires.

### Round-1 issues — both resolved

1. **Existing-conftest collision (was 🔴 blocking) — RESOLVED.** The plan's Fixtures section now states "extend existing file: `tests/ingestion/conftest.py`" and explicitly notes the file already exists (~284 lines) with a `store` fixture bound to `FakeStore`. Verified against ground truth: `tests/ingestion/conftest.py:186` defines `store` returning `FakeStore`, consumed pervasively by `test_episodic_writer.py`. The plan correctly forbids reusing the `store` name and mandates `served_store` for every case in Tasks 1–6, and confirms `pg_pool` is a safe additive name. The stale-spec-line reconciliation is called out in-plan. This removes the green-to-red regression risk.

2. **Bigint case did not exercise > 32 bits (was 🟡) — RESOLVED.** Task 1's large-org case is now pinned to a value strictly above 2³¹ (`2**32 + 7`), with the rationale that `TEST_ORG_ID = 244165546` (< 2³¹, verified at `tests/conftest.py:14`) would pass even against a mistaken `integer` column. The case now genuinely proves the `bigint` column.

### Ground-truth verification of the revised plan
- `_dsn()` defaults (`localhost`/`5432`/`herald_username`/`herald_password`/`herald_database`) match `tests/graph/conftest.py:15-21` exactly.
- `SCHEMA_PATH = parents[2] / "src" / "ingestion" / "schema.sql"` — correct: `parents[2]` from `tests/ingestion/` is the repo root; mirrors the graph conftest's proven pattern.
- `create_pool(_dsn())` import path (`src.core.db`) and single-arg signature confirmed.
- Schema is `CREATE TABLE IF NOT EXISTS served_repos (org_id bigint, repo text, PRIMARY KEY (org_id, repo))` — the composite-PK and `bigint` cases target real constructs; `ON CONFLICT DO NOTHING` and `DELETE ... org_id = $1 AND repo = ANY($2::text[])` match `served_repos.py`.
- Router claims verified at `router.py:230-232`: install-create sets `repos_removed = ()` (line 163) and unconditionally calls `store.remove(org_id, ())`, so Task 4's empty-iterable guard reflects a real hot path; `add` carries the full `repositories` list as the seed path (Task 6).
- `import asyncio` / `asyncio.gather` precedent exists in `tests/graph/test_project_graph_contract.py:1,92` as cited by Task 6.
- Additive fixtures do not collide with root fixtures (`client`/`sign`/`push_payload`/`TEST_ORG_ID`) or the local ingestion fixtures; `test_episodic_writer.py` does not consume `pg_pool`.

### Critical Issues
None.

### Positive Notes
- Case coverage is thorough and each case names the exact construct it pins (composite PK, `ON CONFLICT DO NOTHING`, `org_id = $1` scoping, `list(repos)` normalization, `ORDER BY org_id, repo`, tuple-not-Record mapping). The highest-value cross-tenant `remove` isolation test is correctly foregrounded, and the "populate a second org in every remove case" discipline is stated up front.
- Task 6's order-dependence nuance is right: convergent for different repos, deliberately non-convergent (assert each ordering) for the same repo — matching the real add/remove semantics.
- The one-shot-generator cases for both `add` and `remove` pin single-pass materialization against a future double-iteration refactor — a genuine silent-failure surface.

PLAN_REVIEW_PASS
