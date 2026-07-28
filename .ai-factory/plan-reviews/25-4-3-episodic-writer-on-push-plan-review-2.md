## Code Review Summary

**Artifact reviewed:** Plan `25-4-3-episodic-writer-on-push.md` (v2 — 4 tasks, 4 target files)
**Files cross-checked:** `src/episodic/{store,models,schema.sql,linked_change}.py`, `src/commits/{collector,models}.py`, `src/knowledge/{sync,source_strategy}.py`, `src/github/mirror.py`, `src/llm/embedder.py`, `src/ingestion/{router,models}.py`, `src/main.py`
**Governing spec:** `.ai-factory/specs/25-episodic-writer-on-push.md` (via ROADMAP line 4.3)
**Prior review:** `25-4-3-episodic-writer-on-push-plan-review-1.md` (two issues raised)
**Risk Level:** 🟢 Low — both prior-review issues are resolved; one residual wording imprecision to tighten.

### Context Gates

- **Architecture (`.ai-factory/ARCHITECTURE.md`)** — PASS. The v2 placement (`EpisodicWriter` in `src/ingestion/writer.py`, depending on episodic's public classes via constructor DI) honors both "a feature depends on another feature's *public* class, injected via constructor" (ARCH line 42) and "Logic in entry points" anti-pattern (line 95 — the router only assembles and delegates). No runtime import cycle is introduced: `writer.py → episodic.linked_change → knowledge.source_strategy` terminates (`source_strategy` imports nothing push-shaped); the `knowledge.sync → ingestion.models` edge is on a different module (`sync.py`) not pulled into the writer's import chain.
- **Rules (`.ai-factory/RULES.md`)** — PASS. File is intentionally empty (documented as the correct result); nothing to enforce.
- **Roadmap (`.ai-factory/ROADMAP.md` line 4.3)** — PASS. The line says "wire into `src/ingestion/router.py`" and "the resolve→map→append bridge lives in the router." The plan keeps the *router* thin (delegates to a background task) and relocates the bridge to a class in the same push layer (`src/ingestion/`), which satisfies the roadmap's intent (bridge in the composition/push layer, not inside `src/episodic/`) while honoring the spec's stricter boundary guard.
- **Spec chain** — followed to the leaf: ROADMAP 4.3 → spec 25 → the 4.1/4.2 code it builds on. Spec Guard line 23 ("`src/episodic/` … never imports … anything push-shaped — it only knows `EpisodicEntry`") is now literally satisfied: no new module lands under `src/episodic/`, and the writer sits in `src/ingestion/`. `src/changelog/` confirmed absent; `LinkedChange.completed_tasks` confirmed to hold identifiers; episodic schema confirmed unapplied in `main.py` lifespan (grounding notes 1, 3, 5 all verify true).

### Resolution of prior-review issues

- **Prior Critical Issue 1 (orchestrator placed in `src/episodic/`, violating the push-shaped guard)** — RESOLVED. Task 2 now targets `src/ingestion/writer.py` and grounding note 2 explains the boundary reasoning and why the `KnowledgeSync`-in-`src/knowledge/` precedent is not transplantable (the episodic spec carries the "never anything push-shaped" clause; the knowledge spec does not). The guard holds literally.
- **Prior Minor Issue 2 (`.strip()` before `fromisoformat`)** — RESOLVED. Task 1 now calls out `.strip()` explicitly, with the rationale (`text=True` stdout carries a trailing `\n`; `fromisoformat` raises `ValueError` on it) and cites the existing `_current_branch` precedent.

### Critical Issues

None.

### Minor Issues

**1. Task 1 — the stated import (`import datetime`) is inconsistent with the stated usage (`datetime.fromisoformat`) and would break if followed verbatim.** The task text says "`import datetime` from the stdlib" but the method is annotated `-> datetime` and calls `datetime.fromisoformat(...)`. Under a literal `import datetime` (the module), `datetime.fromisoformat` is an `AttributeError` — `fromisoformat` lives on the `datetime.datetime` *class*, not the module. The intended form is `from datetime import datetime`, which is exactly what the neighboring code already uses (`src/episodic/models.py:2`, `src/episodic/store.py:2`). A competent implementer will infer this from the shown tokens, but the plan should state `from datetime import datetime` so the instruction and the code agree. Non-blocking.

### Positive Notes

- **API/type usage all verified against ground truth.** `LinkedChangeResolver.resolve(repo, before, after)` takes plain strings (`linked_change.py:34`); `change.commits.commits` is `tuple[Commit, ...]` with `.sha`/`.message` (`commits/models.py`); `EpisodicEntry`'s field set exactly matches the Task 2 constructor call (`repo, org_id, completed_tasks, commit_shas, content, embedding, changed_at`, with `recorded_at` defaulted); `Embedder.embed([content])` returns a one-element list, so `[embedding] = await …` destructures safely (`OllamaEmbedder` enforces `len(embeddings) == len(texts)`). No signature or attribute mismatch found.
- **Worktree-path reasoning is correct.** Passing `str(tree)` (a `RepoMirror.tree` worktree at `push.after`) to both `resolve` and `commit_timestamp` is sound — the worktree shares the bare object store, so `before..after`, `before:path`, and `git show <after>` are all reachable (grounding note 4 verified against `mirror.py`).
- **Schema-gap catch remains load-bearing and correctly placed.** `main.py`'s lifespan applies only `SCHEMA_PATH` and `KNOWLEDGE_SCHEMA_PATH`; Task 3's unconditional `episodic/schema.sql` execution (outside the settings-gated block, `CREATE TABLE IF NOT EXISTS`) is required or `append` fails at runtime, and placing it unconditionally means `episodic_entries` exists even when the writer is disabled.
- **`getattr(app.state, "episodic_writer", None)` router guard** mirrors the existing `knowledge_sync` guard (`router.py:87`), keeping the webhook contract tests (which build `TestClient(app)` without running `lifespan`, so `app.state` is unset) returning 200. Registering the episodic task *after* the `knowledge_sync` task matches spec ordering ("after the semantic sync").
- **Name-shadow avoidance is accurate** — `store` is bound to `PgVectorStore` at `main.py:42`; the plan's `episodic_store` local avoids the collision. Reusing the already-built `strategy`, `embedder`, and `mirror` inside the gated block is correct and avoids duplicate construction.
- **Self-contained `mirror.ensure` in the writer** (not depending on `KnowledgeSync.on_push` having fetched first) is the right call — the two background tasks are independent, and worktree reclamation is deferred/guarded in `RepoMirror`.
- **Scoping of the zero-SHA first-push edge is correct.** For `before = "0"*40`, `resolve` → `collector.collect(repo, "000…..after")` runs `git log` with `check=True` and raises `CalledProcessError`; the background task surfaces the failure (consistent with the spec guard "a failure to append raises, never silently drops history"). This is the 4.2 resolver's contract surface, correctly deferred rather than patched here.
- **No branch gate** matches spec line 24 (Phase 4 records every served push, not only canonical-ref pushes) — deliberately unlike 3.6's canonical-ref-only semantic sync.

## Deferred observations

- Affects: Phase 4 write-path efficiency (future report-cadence work, outside this task's file boundary) — On every served push both `KnowledgeSync.on_push` and `EpisodicWriter.write` independently call `mirror.ensure` (a `git fetch --prune`) and open a worktree at `push.after`. This double-fetch is an inherent, acceptable cost of the self-contained design the plan (correctly) chose; if push volume grows it is the natural candidate for a shared per-push mirror-refresh step upstream of both background tasks. (Carried forward from the plan's own deferred note and prior review — no action required for this task.) [dismissed]

Tighten Minor Issue 1's import wording; the plan is otherwise accurate, well-grounded, and ready to implement.
