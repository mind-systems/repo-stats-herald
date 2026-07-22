# Plan Review: 4.1.2 — PgEpisodicStore (impl)

**Plan:** `.ai-factory/plans/22-4-1-2-pgepisodicstore-impl.md`
**Files Reviewed:** plan + reference chain (`src/episodic/store.py`, `src/episodic/models.py`, `src/episodic/schema.sql`, `src/knowledge/store.py`, `src/core/db.py`, `tests/episodic/test_episodic_store_contract.py`, `tests/episodic/conftest.py`, spec `.ai-factory/specs/24-episodic-store.md`)
**Risk Level:** 🟢 Low

### Context Gates
- **Architecture** (`.ai-factory/ARCHITECTURE.md` — feature-modular, constructor DI): PASS. The plan edits only `src/episodic/store.py`; `PgEpisodicStore` receives the pool via constructor (already stubbed), imports only `asyncpg` + `core/db.py` codec + its own model — no cross-feature dependency. Consistent with the "features depend on infra, never each other" rule.
- **Rules** (`.ai-factory/RULES.md`): PASS — file is intentionally empty (no counter-defaults). Nothing to enforce.
- **Roadmap** (`.ai-factory/ROADMAP.md:49`): PASS. Plan is linked to the `4.1.2 — PgEpisodicStore (impl)` contract line, whose `Spec:` names `.ai-factory/specs/24-episodic-store.md`. The plan's tasks match the spec's Change/Guards/Verification one-for-one (pool reuse, `append`=INSERT, `query`=cosine + `changed_at` window, structural append-only, dim-mismatch-raises-by-construction).
- **Skill-context** (`.ai-factory/skill-context/aif-review/SKILL.md`): absent — no project overrides to apply.

### Critical Issues
None.

### Verification against ground truth
Each plan claim was checked against the actual code:

- **`append` column set** matches `schema.sql`: `repo, org_id, completed_tasks, commit_shas, content, embedding, changed_at` — all `NOT NULL`, all present on `EpisodicEntry`. Omitting `recorded_at` correctly lets `DEFAULT now()` fire; this is exactly what `test_since_until_filter_on_changed_at_not_recorded_at` exploits (fresh `recorded_at` vs. old `changed_at`).
- **Tuple→list for `text[]`** (`list(entry.completed_tasks)` / `list(entry.commit_shas)`): correct against the frozen model that stores `tuple[str, ...]`; the reverse hydration back to tuples on `query` is also called out and necessary for the frozen dataclass.
- **Embedding pass-through**: `src/core/db.py` registers a text codec encoding `list[float]` for the `vector` type on every pooled connection, so passing `entry.embedding` straight through is correct and matches `PgVectorStore`. No hand-encoding — plan explicitly forbids it. Good.
- **Dynamic WHERE with lockstep positional params**: the described approach (append each filter value as it adds a `$n`, then `embedding` and `k` last for `ORDER BY embedding <=> $n` / `LIMIT $n`) keeps numbering correct for every combination of `repo`/`since`/`until`. The `<=>` operand type is inferred from the `embedding` column just as in `PgVectorStore` (`ORDER BY embedding <=> $2/$3`), so no explicit `::vector` cast is needed even when the param index shifts.
- **`changed_at` windowing, inclusive bounds**: matches the ABC docstring and the red test's `[t0, t1]` historical assertions; the "never `recorded_at`" hazard from 4.1.1 is explicitly pinned. The recent-window and historical-window arithmetic in the test both resolve correctly under inclusive `>=`/`<=` on `changed_at`.
- **Append-only structural test**: plan forbids adding `update`/`delete`/`upsert`; `test_episodic_store_is_structurally_append_only` asserts their absence on both the ABC and the concrete class. Consistent.
- **File paths / API**: `src/episodic/store.py` is the sole production edit; the stub, ABC, model, and schema exist as described. `conn.execute` / `conn.fetch` / `self._pool.acquire()` usage mirrors `PgVectorStore` exactly. No migration needed — `schema.sql` already ships the table and indexes, and the conftest applies it.

### Positive Notes
- The plan correctly identifies the single most dangerous trap (windowing on `recorded_at` instead of `changed_at`) and pins it, rather than leaving it implicit.
- It anchors every decision to the `PgVectorStore` reference and the registered codec, so the implementer inherits proven pool/vector handling rather than reinventing it.
- Scope discipline is tight: "the only production file to edit is `src/episodic/store.py`" and "the ABC, model, schema, and red suite must not change" — matches the spec's Files & types exactly.

PLAN_REVIEW_PASS
