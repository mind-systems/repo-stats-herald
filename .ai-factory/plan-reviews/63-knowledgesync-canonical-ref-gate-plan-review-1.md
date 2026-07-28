## Plan Review Summary

**Artifact reviewed:** `.ai-factory/plans/63-knowledgesync-canonical-ref-gate.md` (test plan)
**Files planned:** 1 new test file — `tests/knowledge/test_knowledge_sync.py`
**Risk Level:** 🟢 Low

### Context Gates
- **Architecture** (`.ai-factory/ARCHITECTURE.md`): OK. The plan adds only a test under `tests/knowledge/` exercising `src/knowledge/sync.py` through constructor-injected fakes; it introduces no cross-feature import and respects the composition-root / DI boundary. No WARN/ERROR.
- **Rules** (`.ai-factory/RULES.md`): OK. The file is intentionally empty (no project counter-defaults). Nothing to enforce.
- **Roadmap linkage**: OK. The task is the `[ ] **KnowledgeSync canonical-ref gate**` line in `.ai-factory/ROADMAP_TESTS.md`, whose `Spec:` names `.ai-factory/specs/71-knowledge-sync-test-plan.md`. The plan is a faithful decomposition of that governing spec (verified below).

### Governing-spec conformance
Followed the reference chain to the leaf: ROADMAP_TESTS line → spec 71 → `src/knowledge/sync.py` and its collaborators (`RepoMirror`/`resolve_canonical_ref`, `ArtifactIndexer`, `SourceStrategy`/`AiFactorySourceStrategy`, `PushEvent`/`PushCommit`, `CoordinationSeeder`, `KnowledgeStore`, `Embedder`).

All 32 spec cases are covered by the plan's 11 tasks, with none dropped:
- Gate (spec 1–7) → Tasks 1–2
- Changed-path derivation (spec 8–14) → Tasks 3–5
- Tree pinning & fan-out (spec 15–19) → Tasks 6–7
- Backfill (spec 20–29, 31–32) → Tasks 8–10
- Integration (spec 12, 30) → Tasks 5, 11

Ground-truth checks against `sync.py` all hold:
- Constructor signature `KnowledgeSync(mirror, indexer, strategy, canonical_refs, seeder=None)` matches (lines 21–33).
- `on_push` returns before opening `tree` on a non-canonical push (line 60–67), so the gate tests' "zero `tree` calls / `selects` never consulted / seeder not invoked / `ensure` still called once" assertions are all correct; `mirror.ensure` precedes `_canonical_ref` (57–58), and `_canonical_ref` → `resolve_canonical_ref` only touches `default_branch` when `canonical_refs.get(repo)` is `None` (mirror.py 208–218) — the override/default-branch cases are accurate.
- The tree is opened at `push.after`, not the canonical name (line 77) — Task 6 is correctly grounded, and the "log line says `ref=canonical`" trap is real (86–92).
- Index vs remove branches on tree existence, with `remove` strategy-guarded and `index` not (79–84); `ArtifactIndexer.index` internally drops non-selected paths (indexer.py 31–34) — so Task 5's "assert at the store boundary, not the index boundary" is the right layer.
- `backfill` does not pre-filter and skips via `not path.is_file() or ".git" in path.parts` with repo-relative POSIX paths (44–47) — Task 8's `.git`-component-exact and dotfile-passthrough guards, directory-skip, and empty-tree cases all match.
- Seeder fan-out runs after indexing and is skipped when the indexer raises (exception propagates before line 94) — Tasks 7 and 10's ordering/failure-release/no-publish-on-failure assertions hold.

### Fixture-note accuracy
- The `_FakeMirror` model in `tests/graph/test_coordination_seeder.py` uses a **sync** `@contextmanager` `tree` (lines 50–56); the plan correctly requires this and warns against `@asynccontextmanager`. The fake must be extended with an `ensure` recorder (the seeder's fake has none, because `CoordinationSeeder` never calls `ensure` — but `KnowledgeSync` does); the plan states this.
- `async def` fakes for `index`/`remove`/`seed`, `# type: ignore[arg-type]` convention, `asyncio_mode = "auto"` (confirmed in `pyproject.toml`), and the "do not reuse the Postgres `pg_pool`/`store` fixtures" caution all match the codebase.
- The "**Integration cases (12, 30)**" reference in Fixture Notes points to spec 71's case numbers (case 12 = non-curated code paths, case 30 = two-backfill idempotency), which map to plan Tasks 5 and 11 — grounded, not stale.

### Critical Issues
None.

### Positive Notes
- The plan pins the exact regression traps the code invites: hardcoded `"main"` (via a `"trunk"` default branch), `startswith(".git")` vs component-exact, `tree(..., canonical)` vs `tree(..., push.after)`, and hoisting path filtering above the gate. These are the failure modes that would pass a naive suite.
- Correctly insists on set-based assertions given `changed_paths` is a `set` with nondeterministic iteration, while preserving the one real ordering guarantee (all indexing before `seed`) through a shared call log.
- Cleanly separates the two idempotency layers — call-set equality at the `KnowledgeSync` layer (Task 10) vs no-duplicate-chunks at the store layer (Task 11) — matching the spec's gotcha.
- No migration is involved (test-only change; `chunks` schema already exists), and no security surface is touched.

PLAN_REVIEW_PASS
