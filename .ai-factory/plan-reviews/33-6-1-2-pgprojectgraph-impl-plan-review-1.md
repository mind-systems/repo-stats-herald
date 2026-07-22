## Plan Review Summary

**Plan:** `33-6-1-2-pgprojectgraph-impl.md` — 6.1.2 PgProjectGraph (impl)
**Files the plan targets:** `src/graph/store.py`, `src/core/config.py`, `src/main.py`
**Risk Level:** 🟢 Low

The plan is well-grounded: every claim about the codebase checks out against ground truth. The conflict strategy (seed → `ON CONFLICT DO NOTHING`, config → `ON CONFLICT DO UPDATE SET source = EXCLUDED.source`) exactly satisfies the four pinned cases in `tests/graph/test_project_graph_contract.py`, and the hydration/query shapes match the existing `PgEpisodicStore` pattern. The architecture reconciliation (keeping `Settings.project_edges` graph-agnostic as string triples so `core/` never imports the `graph/` feature, then mapping to `Edge(source="config")` at the composition root) is correct and consistent with how `serve_allowlist`/`canonical_refs`/`github_org_logins` already live in `Settings` as primitive/structured types. The findings below are minor and do not undermine the approach.

### Context Gates
- **Architecture** (`.ai-factory/ARCHITECTURE.md`): PASS. The plan explicitly catches the reverse-dependency hazard in spec 09's literal wording ("extend `Settings` … parse into `Edge`s") and resolves it in favor of the dependency rule "Features depend on infra modules, never the reverse." Composition-root wiring in `main.py` conforms to "concretes chosen only at the composition root."
- **Rules** (`.ai-factory/RULES.md`): PASS. File is intentionally empty; no counter-default applies.
- **Roadmap** (`.ai-factory/ROADMAP.md:70`): PASS. Task 6.1.2 line matches the plan intent (seed `DO NOTHING`, config wins, `remove_seed_edges WHERE source='seed'`, load `Settings.project_edges` at startup). `Spec:` → `.ai-factory/specs/09-project-graph-registry.md`, which the plan follows including its guards.
- **Skill-context** (`.ai-factory/skill-context/aif-review/SKILL.md`): absent — no project overrides to apply.

### Critical Issues
None. The store logic, config-parsing shape, and startup wiring are correct and will green 6.1.1's suite.

### Issues / Improvements

1. **`EdgeKind(kind)` will crash on lowercase operator input; spec's own example is lowercase** (`src/main.py`, Task 4). `EdgeKind`'s values are uppercase (`CONTRACT`/`AUTH`/`DEPENDENCY`), so `EdgeKind(kind)` accepts only exact uppercase strings. But spec 09 line 34 documents the operator format with a lowercase example — `a/x > a/y : contract`. An operator following the spec literally would hit a `ValueError` at startup. The plan's own examples happen to use uppercase (line 55), so the plan is internally consistent, but it silently contradicts the governing spec's example and leaves a fragile, operator-facing trap. Recommend normalizing case before enum construction — `EdgeKind(kind.strip().upper())` in Task 4 (or upper-casing the kind token in the Task 3 validator) — and stating the case rule explicitly. This is a value/meaning hole the implementer would otherwise guess at.

2. **New operator env var `PROJECT_EDGES` is not added to `.env.example`** (Task 3 scope). Every existing env-parsed `Settings` field is documented in `.env.example` with a short comment — `SERVE_ALLOWLIST` (line 12–13), `CANONICAL_REFS` (24–26), `GITHUB_ORG_LOGINS` (28–30). The plan introduces `PROJECT_EDGES` (a non-obvious `from>to:kind,...` grammar) but adds no matching `.env.example` entry, leaving the feature undiscoverable and its format unspecified for operators. Add a Task-3 step to document `PROJECT_EDGES` there, mirroring the sibling entries (and, per finding 1, pinning the expected kind casing in that comment). Fixable within the task's natural boundary despite the file not being in the three-file list.

### Positive Notes
- The `source`-branching in `add_edge` and the "config wins by construction, not by load-order timing" reasoning are faithful to spec 09's guard and to the 6.1.1 red suite; `test_config_survives_a_colliding_seed` and `test_idempotent_config_reload` are satisfied by the described SQL.
- Correctly binds `kind` as `edge.kind.value` for the `text` column and hydrates back via `EdgeKind(row["kind"])` — round-trips cleanly since `EdgeKind` is a `StrEnum` whose values equal its member strings.
- Schema wiring follows the established idiom: `GRAPH_SCHEMA_PATH` alongside the other `*_SCHEMA_PATH` constants, applied in the same startup `conn.execute(...)` block; `CREATE TABLE IF NOT EXISTS` is idempotent, so no separate migration mechanism is needed (consistent with how ingestion/knowledge/episodic schemas are applied). No migration gap.
- Places the config load unconditionally (outside the GitHub-App/mirror gate) — correct, since operator edges must load even when canonical-ref sync is disabled.
- Parsing `from>to:kind` by splitting on the first `>` then `:` is safe against `org/repo` names (the `/` never collides with the `>`/`:` delimiters).

## Deferred observations
- Affects: Phase 6 cross-project narration (future consumer) — `neighbors(repo)` as specified (`SELECT to_repo … WHERE from_repo = $1 ORDER BY to_repo`, no `DISTINCT`) can return a duplicate `to_repo` when two edges of different `kind` link the same pair (e.g. `a→b:CONTRACT` and `a→b:DEPENDENCY`). This conforms to the pinned 6.1.1 contract ("the `to_repo` of every edge") and the current tests, so it is correct for this task; flagging only so the eventual neighbors-consumer decides whether it wants distinct project neighbors and de-dupes at that layer.
