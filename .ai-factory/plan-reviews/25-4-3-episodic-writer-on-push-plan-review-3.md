## Code Review Summary

**Artifact reviewed:** Plan `25-4-3-episodic-writer-on-push.md` (v3 — 4 tasks, 4 target files)
**Files cross-checked (fresh, against ground truth):** `src/episodic/{linked_change,models,store,schema.sql}.py`, `src/commits/{collector,models}.py`, `src/knowledge/{sync,source_strategy}.py`, `src/github/mirror.py`, `src/llm/embedder.py`, `src/ingestion/{router,models}.py`, `src/main.py`
**Governing spec:** `.ai-factory/specs/25-episodic-writer-on-push.md` (via ROADMAP line 4.3)
**Prior reviews:** `-plan-review-1.md`, `-plan-review-2.md` (both prior issues resolved in v3)
**Risk Level:** 🟢 Low — every API, type, import, and boundary claim verifies; the sole open item from review 2 (`import datetime` wording) is fixed.

### Context Gates

- **Architecture (`.ai-factory/ARCHITECTURE.md`)** — PASS. Placing `EpisodicWriter` in `src/ingestion/writer.py` and injecting episodic's *public* classes (`EpisodicStore`, `EpisodicEntry`, `LinkedChangeResolver`) by constructor honors "if feature B needs feature A, it depends on A's public class" and the "logic in entry points" anti-pattern (router stays a thin delegator). No import cycle: `src/episodic/{linked_change,models,store}` import only `commits`, `knowledge.source_strategy`, `asyncpg`, `datetime` — nothing from `ingestion` — so `ingestion → episodic` terminates cleanly. Mirrors the existing, accepted `knowledge.sync → ingestion.models` edge in reverse.
- **Rules (`.ai-factory/RULES.md`)** — PASS. File is intentionally empty (documented as the correct state); nothing to enforce.
- **Roadmap (`.ai-factory/ROADMAP.md` line 4.3)** — WARN (informational, non-blocking). The contract line reads "wire into `src/ingestion/router.py`" and "the resolve→map→append bridge lives in the router." The plan relocates the bridge to `src/ingestion/writer.py` (still the push layer) and keeps the router a thin delegator. This is a **justified, documented deviation** (grounding note 2): the spec's stricter Guard (line 23 — `src/episodic/` never imports anything push-shaped) and the ARCHITECTURE "logic in entry points" anti-pattern both point to a class in the push layer rather than resolve/embed/append inlined in the router body. "Lives in the router" is honored in spirit (the bridge lives in the router's package, invoked from the push branch), and the spec — the governing artifact over the contract line's shorthand — is honored literally. Correct deviation = conformance, not a defect.
- **Spec chain** — walked to the leaf: ROADMAP 4.3 → spec 25 → the 4.1/4.2 code it builds on. Spec Guard line 23 is literally satisfied (no new module under `src/episodic/`; writer sits in `src/ingestion/`). `src/changelog/` confirmed absent. Grounding notes 1, 3, 4, 5 all verify true against the code.

### Resolution of prior-review issues

- **Review 2, Minor Issue 1 (`import datetime` vs `from datetime import datetime`)** — RESOLVED. Task 1 now states `from datetime import datetime` explicitly, with the `AttributeError` rationale and the `src/episodic/models.py:2` precedent. Instruction and shown usage (`datetime.fromisoformat`, `-> datetime`) now agree.
- **Review 1 Critical (orchestrator in `src/episodic/` violating the push-shaped guard)** — RESOLVED and re-confirmed in v3 (writer in `src/ingestion/writer.py`).

### Critical Issues

None.

### Minor Issues

None blocking. Every instruction is implementable as written and produces correct code.

### API / ground-truth verification (all confirmed)

- **`LinkedChangeResolver.resolve(repo, before, after)`** takes plain strings (`linked_change.py:34`); `LinkedChange.completed_tasks: tuple[str, ...]`, `.commits: CommitContext`. Passing `str(tree)` is correct.
- **`CommitContext.commits: tuple[Commit, ...]`**, `Commit.sha` / `Commit.message` exist (`commits/models.py`). Task 2's `content` join and `commit_shas=tuple(c.sha …)` are type-correct.
- **`EpisodicEntry`** field set (`repo, org_id, completed_tasks, commit_shas, content, embedding, changed_at, recorded_at=None`) exactly matches the Task 2 constructor call; omitting `recorded_at` lets the DB `DEFAULT now()` fill it (`schema.sql:12`, `store.append` inserts no `recorded_at`).
- **`Embedder.embed([content])`** returns a one-element list (`OllamaEmbedder` enforces `len(embeddings) == len(texts)` and rejects empty vectors), so `[embedding] = await …` destructures safely.
- **`RepoMirror.ensure(repo, org_id)`** and **`tree(repo, org_id, ref)`** (a `contextmanager` yielding `Path`) match Task 2 usage. Deferred worktree reclamation means the two background tasks' independent `ensure`/`tree` calls are safe; Starlette runs background tasks sequentially (knowledge_sync completes before episodic_writer starts), so no concurrent-worktree race for a single request.
- **`GitCommitCollector`** has no `commit_timestamp` today — Task 1 adds it. `git show -s --format=%cI --end-of-options <ref>` yields strict ISO-8601 with offset; `datetime.fromisoformat` (3.12) parses it to an aware datetime; `.strip()` is correctly flagged as required (trailing `\n`), mirroring `_current_branch`.
- **Composition root wiring:** `store` is already bound to `PgVectorStore` at `main.py:42`, so the plan's distinct `episodic_store` local avoids the shadow. `LinkedChangeResolver(collector, strategy)` matches `__init__(collector, source_strategy)`; `strategy.roadmap_paths()` exists (`source_strategy.py:56`), so reusing the built `AiFactorySourceStrategy` is valid. `EpisodicWriter(mirror, resolver, embedder, episodic_store, collector)` matches the Task 2 constructor order. All four imports resolve to real symbols.
- **Schema application:** `main.py`'s lifespan applies only `SCHEMA_PATH` and `KNOWLEDGE_SCHEMA_PATH` today — the episodic table is genuinely unapplied, so Task 3's unconditional `episodic/schema.sql` execution is load-bearing (else `append` fails at runtime). `schema.sql` is idempotent (`CREATE EXTENSION/TABLE/INDEX … IF NOT EXISTS`), safe to run every startup and even when the writer is disabled.
- **Router guard:** `getattr(request.app.state, "episodic_writer", None)` mirrors the existing `knowledge_sync` guard (`router.py:87-89`), keeping the contract tests (which build `TestClient(app)` without running `lifespan`, so `app.state` is unset) returning their existing status. Registering the episodic task *after* the knowledge_sync task matches the spec's "after the semantic sync" ordering.

### Positive Notes

- **No-branch-gate decision is correct** and matches spec line 24 (Phase 4 records every served push, deliberately unlike 3.6's canonical-ref-only semantic sync) — grounding note 6 is accurate.
- **Zero-SHA first-push edge is correctly scoped out.** For `before = "0"*40`, `resolve` → `collector.collect(repo, "000…..after")` runs `git log` with `check=True` → `CalledProcessError`; the background task surfaces it (spec guard: "a failure to append raises, never silently drops history"). This is the 4.2 resolver's contract surface, correctly flagged for verification and deferred to a 4.2 follow-up rather than patched here.
- **Write-path stays cheap** — exactly one `embed` call, no `LLMClient.generate`; outcome derivation is correctly left to the read-time reasoner (spec Guard line 22).
- **Self-contained `mirror.ensure`** in the writer (not depending on `KnowledgeSync.on_push` having fetched first) is the right call for two independent background tasks.

## Deferred observations

- Affects: Phase 4 write-path efficiency (future report-cadence work, outside this task's file boundary) — On every served push both `KnowledgeSync.on_push` and `EpisodicWriter.write` independently call `mirror.ensure` (a `git fetch --prune`) and open a worktree at `push.after`. This double-fetch is an inherent, acceptable cost of the self-contained design the plan (correctly) chose; if push volume grows it is the natural candidate for a shared per-push mirror-refresh step upstream of both background tasks. [dismissed]

The plan is accurate, fully grounded against the current code, and ready to implement.

PLAN_REVIEW_PASS
