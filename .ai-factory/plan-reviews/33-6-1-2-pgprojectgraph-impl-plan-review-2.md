## Plan Review Summary

**Plan:** `33-6-1-2-pgprojectgraph-impl.md` — 6.1.2 PgProjectGraph (impl)
**Files the plan targets:** `src/graph/store.py`, `src/core/config.py`, `.env.example`, `src/main.py`
**Risk Level:** 🟢 Low

Round-2 review. Both findings raised in `33-...-plan-review-1.md` have been resolved in the plan text:
- **Finding 1 (lowercase-operator `EdgeKind` crash)** — Task 3 now normalizes the `kind` token to upper-case in the validator (`kind.strip().upper()`) and Task 4 notes the token "arrives already upper-cased," so `EdgeKind(kind)` accepts spec 09's own lowercase example (`a/x > a/y : contract`) without a startup `ValueError`. The case rule is stated explicitly.
- **Finding 2 (`PROJECT_EDGES` missing from `.env.example`)** — Task 3 now includes an `.env.example` step (entry after the `GITHUB_ORG_LOGINS` block, documenting the grammar, the case-insensitive kind, an example, and a blank value), and `.env.example` is added to the Task-3 file list.

The plan remains well-grounded: the store's conflict strategy, hydration shapes, config-parsing idiom, and startup wiring all check out against ground truth and against the pinned 6.1.1 suite.

### Context Gates
- **Architecture** (`.ai-factory/ARCHITECTURE.md`): PASS. The plan's central reconciliation still holds — `Settings.project_edges` stays graph-agnostic (string triples), so `src/core/` never imports the `src/graph/` feature, satisfying "Features depend on infra modules, never the reverse" (ARCHITECTURE.md:41). The `Edge(source="config")` mapping and `EdgeKind` construction happen only in `src/main.py`, the composition root, per "Concrete implementations are chosen only at the composition root" (ARCHITECTURE.md:43). Consistent with how `serve_allowlist`/`canonical_refs`/`github_org_logins` already live as primitive/structured `Settings` fields.
- **Rules** (`.ai-factory/RULES.md`): PASS. File is intentionally empty (its own note confirms no counter-default surfaced); nothing to enforce.
- **Roadmap** (`.ai-factory/ROADMAP.md:70`): PASS. The 6.1.2 contract line matches the plan intent point-for-point (seed `ON CONFLICT DO NOTHING` so config wins, `remove_seed_edges WHERE source='seed'`, load `Settings.project_edges` tagged `source=config` at startup, greening 6.1.1). `Spec:` → `.ai-factory/specs/09-project-graph-registry.md`, whose Change/Guards/Verification the plan follows, including the reverse-dependency reconciliation of the spec's literal "parse into `Edge`s" wording.
- **Skill-context** (`.ai-factory/skill-context/aif-review/SKILL.md`): absent — no project overrides to apply.

### Critical Issues
None. The described SQL greens all four pinned cases in `tests/graph/test_project_graph_contract.py`:
- `test_config_survives_a_colliding_seed` — config INSERT then seed INSERT with `DO NOTHING` leaves `source='config'`. ✓
- `test_seed_only_removal` — `DELETE ... WHERE from_repo=$1 AND source='seed'` drops the seed edge, keeps the config edge. ✓
- `test_directed_neighbors` — `SELECT to_repo WHERE from_repo=$1 ORDER BY to_repo` returns `["b"]` for `a`, `[]` for `b`. ✓
- `test_idempotent_config_reload` — config INSERT twice with `DO UPDATE SET source=EXCLUDED.source` yields one row. ✓

### Positive Notes
- `add_edge` binds `kind` as `edge.kind.value` for the `text` column and hydrates back via `EdgeKind(row["kind"])`; round-trips cleanly since `EdgeKind` is a `StrEnum` whose values equal its member strings.
- Store methods correctly follow the `PgEpisodicStore` pattern (`async with self._pool.acquire()`, parameterized SQL, row→value-object hydration) — matches `src/episodic/store.py` exactly.
- `Settings.project_edges` uses the established `Annotated[..., NoDecode]` + `@field_validator(mode="before")` idiom (mirroring `serve_allowlist`); default `()` with no env var behaves like the existing fields (before-validator not invoked on the default).
- Parsing `from>to:kind` by splitting on the first `>` then `:` is safe against `org/repo` names — `/` collides with neither delimiter.
- Schema wiring follows the idiom: `GRAPH_SCHEMA_PATH` alongside the sibling `*_SCHEMA_PATH` constants, applied in the same startup `conn.execute(...)` block; `CREATE TABLE IF NOT EXISTS` is idempotent so no separate migration mechanism is needed — consistent with ingestion/knowledge/episodic. No migration gap.
- Config load is placed unconditionally, outside the GitHub-App/mirror gate in `lifespan` — correct, since operator edges must load even when canonical-ref sync is disabled.

## Deferred observations
- Affects: Phase 6 cross-project narration (future `neighbors` consumer) — `neighbors(repo)` as specified (`SELECT to_repo … WHERE from_repo = $1 ORDER BY to_repo`, no `DISTINCT`) can return a duplicate `to_repo` when two edges of different `kind` link the same ordered pair (e.g. `a→b:CONTRACT` and `a→b:DEPENDENCY`). This conforms to the pinned 6.1.1 contract ("the `to_repo` of every edge `repo -> ...`") and passes the current tests, so it is correct for this task; flagging only so the eventual neighbors-consumer decides whether it wants distinct project neighbors and de-dupes at that layer. [dismissed]

PLAN_REVIEW_PASS
