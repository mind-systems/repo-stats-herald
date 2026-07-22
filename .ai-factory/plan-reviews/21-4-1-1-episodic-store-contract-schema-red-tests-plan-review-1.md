## Code Review Summary

**Files Reviewed:** 1 plan (`21-4-1-1-episodic-store-contract-schema-red-tests.md`), verified against the governing spec (`.ai-factory/specs/44-episodic-store-contract.md`), the roadmap contract line (4.1.1), and the mirrored ground-truth code (`src/knowledge/store.py`, `src/knowledge/schema.sql`, `src/core/db.py`, `tests/knowledge/conftest.py`, `tests/knowledge/test_knowledge_store_contract.py`).
**Risk Level:** 🟢 Low

### Context Gates
- **Architecture** (`.ai-factory/ARCHITECTURE.md`): PASS. The plan places `EpisodicEntry` in `src/episodic/models.py` (the feature template's home for value objects) rather than inlining it as knowledge did with `Chunk` — the plan calls out this deliberate deviation and it is the *more* architecture-conformant choice (`src/commits/models.py` confirms the pattern is live). Feature-depends-on-infra-only holds: `src/episodic/` will import `src/core/db.create_pool` and nothing from another feature.
- **Rules** (`.ai-factory/RULES.md`): PASS. File is intentionally empty (no project counter-defaults); nothing to violate.
- **Roadmap** (`.ai-factory/ROADMAP.md` line 48, task 4.1.1): PASS. The plan matches the contract line point-for-point — `episodic_entries` columns, `vector(<dim>)`→`vector(768)`, ANN cosine index + `(repo, changed_at)` btree, `EpisodicEntry` model, `EpisodicStore` ABC with `append`/`query(embedding,k,repo,since,until)` naming no Postgres concept, the three red tests (cosine rank; `changed_at`-specific windowing with planted misleading `recorded_at`; structural append-only with no mutation method). The Spec link resolves.
- **Skill-context** (`.ai-factory/skill-context/aif-review/SKILL.md`): absent — gate skipped.

### Critical Issues
None. The plan is faithful to the spec and to the proven knowledge-store shapes. File paths (`src/episodic/`, `tests/episodic/`, `src/core/db.py`), the `create_pool(_dsn())` API, the `vector` text codec marshaling as `list[float]`, `vector(768)` matching the `chunks` column and 3.2's embedder, `asyncio_mode = "auto"` (so async tests need no decorator), and the schema-apply-then-`TRUNCATE` fixture shape are all verified correct against ground truth. Dataclass field ordering is valid (only `recorded_at` carries a default, and it is last). The structural test is sound (`object` exposes no `update`/`delete`/`upsert`, and `PgEpisodicStore` adds none). No migration system exists in this repo — schema is applied by the conftest fixture exactly as knowledge does — so there is no missing-migration gap.

### Findings

**1. The windowing test's timestamp handling is unspecified — a real, in-scope footgun in territory the mirrored knowledge tests never touched (Task 4 `make_entry` / Task 5 windowing test).**
This is the episodic store's first use of timestamps; the knowledge tests carry no `timestamptz` precedent to inherit, and the plan tells the implementer to "plant historical timestamps" and pass `since`/`until` without pinning timezone-awareness. Verified against asyncpg's own encoder (`asyncpg/pgproto/codecs/datetime.pyx`):
  - `timestamptz_encode` does `obj.astimezone(utc)`. A **naive** datetime does not raise — Python's `.astimezone()` assumes it is **local time** and shifts it by the machine's UTC offset. So naive `since`/`until` boundaries silently move by the local offset, making the pass/fail of a boundary-adjacent window **environment-dependent (flaky across timezones)**.
  - `timestamptz_decode` returns **tz-aware** (UTC) datetimes. Any Python-side comparison in the test between a returned `changed_at`/`recorded_at` and a naive reference raises `TypeError: can't compare offset-naive and offset-aware datetimes`.

  Why it matters here specifically: the `changed_at`-vs-`recorded_at` window test *is* the adversarial core of 4.1.1. A local-offset-shifted boundary could move a planted "just in-window" or "just out-of-window" timestamp across the edge and mask the very wrong-column bug the test exists to catch. Recommend the plan pin: build all planted `changed_at` values and `since`/`until` boundaries as timezone-aware (`datetime.now(timezone.utc)` and aware offsets), and keep the misleading `recorded_at` distance from the window comfortably larger than any conceivable local offset so the assertions stay unambiguous regardless of test-host timezone. Low severity, but concrete and fixable within this task's boundary.

### Positive Notes
- The adversarial framing of the windowing test is well-specified in both directions (must-not-leak-in on an old `changed_at` + fresh `recorded_at`; must-not-leak-out on an in-window `changed_at` + out-of-window `recorded_at`), directly satisfying the spec's "a merely-passing 'query returns something' test would not catch the wrong column" guard.
- The plan correctly anticipates that the structural append-only test is green-from-the-start and is honest about it not carrying the red — the two behavioral tests carry the red via the raising stub. This matches the spec exactly and avoids a false "all tests red" claim.
- `recorded_at: datetime | None = None` on the model, with the real value assigned by the DB `now()` default, is the right split — callers appending fresh entries need not fabricate an ingest time, and it keeps the model pure/I-O-free.
- Correctly requires `CREATE EXTENSION IF NOT EXISTS vector;` + `IF NOT EXISTS` on table/index so the schema applies idempotently alongside `chunks` on the same database.
