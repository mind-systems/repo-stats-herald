## Code Review Summary

**Artifact reviewed:** Plan `25-4-3-episodic-writer-on-push.md` (4 tasks, 4 target files)
**Files cross-checked:** `src/episodic/{store,models,schema.sql,linked_change}.py`, `src/commits/collector.py`, `src/knowledge/{sync,source_strategy}.py`, `src/github/mirror.py`, `src/llm/embedder.py`, `src/ingestion/{router,models}.py`, `src/main.py`
**Governing spec:** `.ai-factory/specs/25-episodic-writer-on-push.md` (via ROADMAP line 4.3)
**Risk Level:** 🟡 Medium — one architectural conflict with the governing spec to reconcile; everything else is sound and well-grounded.

### Context Gates

- **Architecture (`.ai-factory/ARCHITECTURE.md`)** — WARN. The plan's core move (orchestrator class invoked by a thin router, not logic in the router body) correctly honors ARCHITECTURE's "Logic in entry points" anti-pattern and the `KnowledgeSync` precedent. But its *placement* of that orchestrator (see Critical Issue 1) collides with a stricter, feature-specific guard in the governing spec. The two are reconcilable — the plan just picked the one placement that isn't.
- **Rules (`.ai-factory/RULES.md`)** — PASS. File is intentionally empty; nothing to enforce.
- **Roadmap (`.ai-factory/ROADMAP.md` line 4.3)** — WARN. Roadmap says "wire into `src/ingestion/router.py`" and "the resolve→map→append bridge lives in the router"; spec says "at the composition/router layer — never inside the `episodic` package itself." The plan's deviation from *router-body* placement is defensible, but its chosen destination (`src/episodic/`) contradicts the spec's boundary clause (Critical Issue 1).
- **Spec chain** — followed to the leaf: ROADMAP 4.3 → spec 25 → the 4.1/4.2 code it builds on. `src/changelog/` confirmed absent (grounding note 1 verified true); `LinkedChange.completed_tasks` confirmed to hold identifiers, not titles (grounding note 3 verified true); episodic schema confirmed unapplied in `main.py` lifespan (grounding note 5 verified true).

### Critical Issues

**1. Placing `EpisodicWriter` in `src/episodic/writer.py` violates the spec's explicit boundary guard, and the plan's justification quotes only half of that guard.**

Spec 25, Guard line 23 (verbatim): *"the router imports both `episodic` and (later) `changelog`; `src/episodic/` itself never imports `src/changelog/` **or anything push-shaped** — it only knows `EpisodicEntry`."*

Task 2 puts `EpisodicWriter` under `src/episodic/`, has it `import PushEvent from src.ingestion.models`, and gives it `async def write(self, push: PushEvent)`. `PushEvent` is exactly "something push-shaped." Today `src/episodic/` is genuinely push-agnostic (`linked_change.resolve` takes `repo, before, after` strings, not a `PushEvent`); this plan would make `writer.py` the first module in the package to import a push type — the precise thing the guard forbids.

Grounding note 2 declares the guard satisfied because the writer "imports … never `changelog` … so the actual guard holds." That reasoning addresses only the `changelog` half and silently drops the "or anything push-shaped — it only knows `EpisodicEntry`" half. The guard is not satisfied.

Note this is a plan-vs-**governing-spec** conflict, not an implementer-vs-stale-description deviation: the spec states intended architecture ahead of the code, and the code is verified against it. So the DEVIATION latitude for "the file disagreed with the plan, follow the file" does not apply here — there is a real defect to reconcile before implementation.

The plan frames the choice as a false dichotomy — *logic-in-router-body* (which ARCHITECTURE forbids) vs. *orchestrator-in-`src/episodic/`* — and misses the third option that satisfies **both** constraints: place the orchestrator **outside** `src/episodic/`, in the composition/push layer. Concretely:

- Put `EpisodicWriter` in `src/ingestion/` (the push feature already owns `PushEvent`), or in a small composition/bridge module the router calls. It may depend on episodic's *public* classes (`EpisodicStore`, `EpisodicEntry`, `LinkedChangeResolver`) — ARCHITECTURE allows "if feature B needs feature A, it depends on A's public class." `src/episodic/` then keeps knowing only `EpisodicEntry`, and the guard holds literally.
- The `KnowledgeSync`-in-`src/knowledge/sync.py` precedent the plan leans on is not symmetric: the *knowledge* spec carries no "never anything push-shaped" clause, whereas the *episodic* spec does. The asymmetry is deliberate in the specs, so the precedent cannot be transplanted.

Either relocate the orchestrator so `src/episodic/` imports nothing push-shaped, or, if the in-package placement is truly intended, get spec 25's Guard amended first (the plan cannot unilaterally override a governing guard it also misquotes). All Task 2/Task 3 import lists and the `writer.py` path change accordingly.

### Minor Issues

**2. `commit_timestamp` must strip `git`'s trailing newline before `fromisoformat`.** Task 1 specifies `datetime.fromisoformat(...)` over `git show -s --format=%cI …` output, but `subprocess.run(..., text=True).stdout` carries a trailing `\n`, and `datetime.fromisoformat("2026-07-22T…+03:00\n")` raises `ValueError`. The existing collector methods (`_current_branch`) already `.strip()`; the plan should say `.strip()` explicitly so the implementer mirrors that. Otherwise the approach is correct: `%cI` yields an offset-aware ISO-8601 string, `fromisoformat` returns an aware `datetime`, and the `changed_at timestamptz` column accepts it.

### Positive Notes

- **Schema-gap catch is correct and load-bearing.** `main.py`'s lifespan applies only the ingestion and knowledge schemas; without Task 3's unconditional `episodic/schema.sql` execution, `append` would fail at runtime. Placing it alongside the other two (outside the settings-gated block) is right — `episodic_entries` then exists even when the writer is disabled, and it's `CREATE TABLE IF NOT EXISTS`, so idempotent.
- **Self-contained `mirror.ensure` in the writer** (not relying on `KnowledgeSync.on_push` having fetched first) is the correct call — the two background tasks are independent, and worktree reclamation is already deferred/guarded in `RepoMirror`.
- **`getattr(app.state, "episodic_writer", None)` guard** correctly mirrors the `knowledge_sync` pattern, keeping the webhook contract tests (which build `TestClient(app)` without running `lifespan`) green — verified against `router.py` line 87.
- **Name-shadow warning is accurate** — `store` is already bound to `PgVectorStore` in the gated block (`main.py` line 42); using `episodic_store` avoids the collision.
- **Grounding notes 1, 3, 5 all verify true** against the code, and the "no branch gate / records every served push" reading matches spec line 24. Deferring the zero-SHA first-push edge to 4.2 (the resolver's contract surface) rather than patching the writer is the right scoping call.

## Deferred observations

- Affects: Phase 4 write-path efficiency (future report-cadence work, not this task's file boundary) — On every served push both `KnowledgeSync.on_push` and `EpisodicWriter.write` independently call `mirror.ensure` (a `git fetch --prune`) and open a worktree at `push.after`. This double-fetch is an inherent, acceptable cost of the self-contained design the plan (correctly) chose, but if push volume grows it is the natural candidate for a shared per-push mirror-refresh step upstream of both background tasks. [dismissed]

Reconcile Critical Issue 1 before implementation; the remainder of the plan is accurate and ready.
