## Code Review Summary

**Files Reviewed:** 1 plan (`21-4-1-1-episodic-store-contract-schema-red-tests.md`), verified against the governing spec (`.ai-factory/specs/44-episodic-store-contract.md`), the roadmap contract line (4.1.1), and the mirrored ground-truth code (`src/knowledge/store.py`, `src/knowledge/schema.sql`, `src/core/db.py`, `tests/knowledge/conftest.py`, `tests/knowledge/test_knowledge_store_contract.py`, `pyproject.toml`).
**Risk Level:** 🟢 Low

### Context Gates
- **Architecture** (`.ai-factory/ARCHITECTURE.md`): PASS. The plan places `EpisodicEntry` in `src/episodic/models.py` (the feature template's home for value objects) rather than inlining it as knowledge did with `Chunk`. Task 3 calls this out as a deliberate, *more* architecture-conformant choice. Feature-depends-on-infra-only holds: `src/episodic/` imports only `src/core/db.create_pool` and stdlib/asyncpg, nothing from another feature.
- **Rules** (`.ai-factory/RULES.md`): PASS. File is intentionally empty (its own note states this is the correct result, not a gap); nothing to violate.
- **Roadmap** (`.ai-factory/ROADMAP.md` line 49, task 4.1.1): PASS. The plan matches the contract line point-for-point — `episodic_entries` columns, `vector(<dim>)`→`vector(768)`, ANN cosine index + `(repo, changed_at)` btree, `EpisodicEntry` model, `EpisodicStore` ABC with `append`/`query(embedding,k,repo,since,until)` naming no Postgres concept, and the three red tests (cosine rank; `changed_at`-specific windowing with a planted misleading `recorded_at`; structural append-only with no mutation method). The `Spec:` link resolves and the spec's Change/Guards/Verification sections are each satisfied.
- **Skill-context** (`.ai-factory/skill-context/aif-review/SKILL.md`): absent — gate skipped.

### Prior review disposition
Plan-review-1 raised a single finding: the windowing test's timezone handling was unspecified — a real footgun since this is the store's first `timestamptz` use and the knowledge tests carry no precedent. **This is now fully resolved in the plan.** Task 4 adds an explicit "Timestamps are timezone-aware, always" clause with the asyncpg-verified rationale (naive datetimes silently shift by the host UTC offset on encode; the decoder returns tz-aware UTC so naive comparisons raise `TypeError`), pins a fixed aware default (`datetime(2024, 1, 1, tzinfo=timezone.utc)`), and Task 5 requires all `changed_at`/`since`/`until` values to be tz-aware UTC with day/week gaps kept "comfortably larger than any host UTC offset" so no boundary sits offset-adjacent. The fix is correct and matches asyncpg's actual `timestamptz` codec behavior.

### Critical Issues
None. The plan is faithful to the spec and to the proven knowledge-store shapes, verified against ground truth:
- File paths (`src/episodic/`, `tests/episodic/`, `src/core/db.py`, `src/episodic/schema.sql`) and the `create_pool(_dsn())` API are correct; neither `src/episodic/` nor `tests/episodic/` exists yet, so all files are genuinely new.
- `asyncio_mode = "auto"` is confirmed in `pyproject.toml`, so the async `pg_pool` fixture and async test functions need no decorators — the mirrored conftest/test shape works as-is.
- The `vector` codec registered in `create_pool`'s `init` marshals embeddings as `list[float]` on both ends; `vector(768)` matches the `chunks` column and 3.2's embedder.
- Dataclass field ordering is valid: only `recorded_at` carries a default and it is last. The `recorded_at: datetime | None = None` split (real value from the DB `now()` default) is the right call and keeps the model pure — the plan justifies the deviation from the spec's bare `recorded_at: datetime`.
- The structural append-only test is sound: `object` exposes no `update`/`delete`/`upsert`, and `PgEpisodicStore` defines only `append`/`query`, so the `not hasattr(...)` assertions hold. The plan is honest that this test is green-from-the-start and that the two behavioral tests carry the red via the raising stub — matching the spec exactly.
- No migration system exists in this repo; the schema is applied by the conftest fixture (schema-apply-then-`TRUNCATE`), exactly as knowledge does — no missing-migration gap. `CREATE EXTENSION / TABLE / INDEX IF NOT EXISTS` make it idempotent alongside `chunks` on the same DB.

### Positive Notes
- The adversarial windowing test is well-specified in both directions (must-not-leak-in on old `changed_at` + fresh `recorded_at`; must-not-leak-out on in-window `changed_at` + out-of-window `recorded_at`), directly satisfying the spec's guard that a merely-passing "query returns something" test would not catch the wrong column.
- The cosine-order test mirrors the proven knowledge test precisely (distance 0 / 1 / 2 via same-direction, orthogonal, opposite unit vectors) and asserts exact order so a reversed `ORDER BY` cannot pass.
- The append-only guarantee is correctly modeled as *structural* (no mutation method exists on the ABC) rather than a runtime check — the plan pins this as a regression guard against a future task quietly adding a mutation method.
- Because pgvector applies `WHERE` before `LIMIT`, the k value chosen for the windowing test does not create a false pass on the must-not-leak-in assertion; the plan's instruction to mirror the knowledge test (which sizes k to the planted-entry count) covers the must-not-leak-out direction as well.

PLAN_REVIEW_PASS
