## Code Review Summary

**Artifact reviewed:** `.ai-factory/plans/20-3-6-populate-and-keep-fresh.md` (plan for task 3.6 — Populate and keep fresh)
**Files the plan targets:** `src/core/config.py`, `.env.example`, `src/github/mirror.py`, `src/knowledge/sync.py` (new), `src/main.py`, `src/ingestion/router.py`, `scripts/backfill.py` (new)
**Risk Level:** 🟢 Low

Reviewed against the governing spec `.ai-factory/specs/08-populate-and-refresh.md` (reached via the ROADMAP 3.6 contract line), the ARCHITECTURE dependency rules, and the actual code of every collaborator the plan wires (`RepoMirror`, `ArtifactIndexer`, `AiFactorySourceStrategy`, `PgVectorStore`, `OllamaEmbedder`, `GitHubAppAuth`, `PushEvent`, the webhook router, and the webhook-contract test suite).

### Context Gates

- **Architecture (`.ai-factory/ARCHITECTURE.md`)** — PASS. `KnowledgeSync` lives in the `knowledge` feature and receives `RepoMirror` (the `github` feature's public class) via constructor injection, wired only at the composition root — exactly the sanctioned "feature B depends on feature A's public class, injected via constructor" form, not an internal-file import. All concretes (`OllamaEmbedder`, `PgVectorStore`, `AiFactorySourceStrategy`, `ArtifactIndexer`, `GitHubAppAuth`, `RepoMirror`) are assembled in `main.py` / `scripts/backfill.py` only; `Settings` is read at the root and passed down as primitives. No cross-feature internal reach, no env read inside a feature, no logic in entry points. Conforms.
- **Rules (`.ai-factory/RULES.md`)** — PASS (file intentionally empty; nothing to enforce).
- **Roadmap (`.ai-factory/ROADMAP.md`)** — PASS, with one linkage note. The plan maps cleanly onto the 3.6 contract line and its guards (canonical-ref-only, no per-branch store, removed paths deleted, idempotent, wire `on_push` after the serve-allowlist). See Deferred observations for the 3.5→3.6 "on-install backfill" linkage.
- **Project skill-context (`.ai-factory/skill-context/aif-review/SKILL.md`)** — absent; no project-specific review overrides.

### Critical Issues

None. The plan is internally consistent, grounded in the real signatures of every collaborator, and each verification bullet is achievable as written.

Spot-checks that passed against ground truth:
- **`clone_source` needs an org login the fixed `(repo, org_id)` signature can't carry (Assumption 3).** Confirmed: `RepoMirror.ensure` calls `self._clone_source(repo, org_id)` with only `org_id`, and `backfill` has no `PushEvent` to read `org_login` from. The `Settings.github_org_logins` map is genuinely required, not redundant. `dict[int, str]` parses from env JSON with pydantic key-coercion (`{"244165546":"mind-systems"}` → `int` key).
- **`on_push` changed-path handling (Assumption 2 / Task 3).** Correct and necessary asymmetry: `index` self-gates on `SourceStrategy.selects` (verified in `indexer.py`), but `remove` does **not** self-gate (`ArtifactIndexer.remove` calls `store.delete` unconditionally) — so the plan's explicit `elif strategy.selects(path)` before `remove` is exactly what keeps a code-only deletion from doing store work. Presence-at-`after` via `(tree / path).is_file()` correctly resolves the "modified then later deleted in the same push" case.
- **Canonical ref reads from mirror `HEAD` (Task 2).** A `git clone --mirror` stores branches under `refs/heads/*` and sets bare `HEAD` to the origin default; `git symbolic-ref --short HEAD` in the bare store yields e.g. `main`, and `tree(repo, org_id, "main")` / `tree(..., push.after)` both resolve locally after `ensure`'s fetch. Order is right: `ensure` precedes any `default_branch` call in both `backfill` and `on_push`.
- **Test-suite bootability (Assumption "gated, not hard-asserting" / Task 5).** Confirmed against `tests/conftest.py`: the client fixture is `TestClient(app)` used **without** the context-manager form, so `lifespan` never runs and `app.state.knowledge_sync` is unset. The `getattr(..., "knowledge_sync", None)` guard skips `on_push`, and the push branch still returns `JSONResponse(jsonable_encoder(event))` — the 2.1.x contract stays green.
- **BackgroundTasks + direct `Response` return.** Valid: FastAPI attaches the request's collected `BackgroundTasks` to a directly-returned `Response` whose `.background is None`, so `background_tasks.add_task(knowledge_sync.on_push, event)` still fires. `on_push` being a coroutine is supported.
- **Embedding dimension.** `schema.sql` declares `vector(768)`; default `embed_model = "nomic-embed-text"` (768-dim) matches. Applying `src/knowledge/schema.sql` at the root and in the backfill script is idempotent (`CREATE ... IF NOT EXISTS`), and the existing dev flow pre-creates the `vector` extension, so `CREATE EXTENSION IF NOT EXISTS` is a privilege-safe no-op.

### Positive Notes

- Assumptions section is unusually rigorous — each non-obvious decision (canonical-ref resolution, state-at-`after` path handling, the org-login map, the gated composition root, the background-task ack) is stated with its reason and traced to a real constraint in the code.
- Correctly folds in the files the spec's *prose* requires but its explicit file list omits (`main.py`, `mirror.py`, `scripts/backfill.py`), and says so (Assumption "Scope beyond the spec's explicit file list").
- The startup `sweep_worktrees()` addition (Task 2) discharges the disk-leak guard the `RepoMirror` docstring explicitly assigns to "the consuming task" — the plan is the first live composition root, so this is the right place for it.
- Idempotency is reasoned from the store's actual contract (`upsert` is delete-then-insert per `(repo, path)`), not asserted.

## Deferred observations

- Affects: task 3.4 boundary (`src/knowledge/source_strategy.py` / `src/knowledge/indexer.py`) — `AiFactorySourceStrategy.selects` returns `True` for **anything** under `docs/` (`_PREFIXES` + `startswith`), while `ArtifactIndexer.index` reads the file with `(tree / path).read_text(encoding="utf-8")` unconditionally after selection. A repository with a binary asset under `docs/` (e.g. `docs/img/diagram.png`) will raise `UnicodeDecodeError`. `backfill` is the first consumer to walk an entire tree and feed every selected path, so it is where this latent issue first surfaces (at scale, and fatally for the whole backfill run). The fix belongs in the strategy/indexer that own selection and reading — outside this task's file boundary — so it is deferred, but the 3.6 implementer/tester should be aware backfill on a docs-with-binaries repo can crash. [dismissed]

- Affects: a later phase / the 3.5→3.6 linkage — the 3.5 contract line states the `served_repos` set is "consumed by **3.6's on-install backfill**," yet this plan ships only a manual `scripts/backfill.py --repo --org-id` entrypoint and never consumes `served_repos` (no auto-backfill on `installation`). The governing spec (08) explicitly permits this ("triggered manually / on install; a small entrypoint is enough here"), so the plan does not violate its own contract — but the on-install auto-backfill expectation set by 3.5 remains unwired and should be tracked for a follow-up rather than assumed delivered here. [routed → .ai-factory/specs/55-on-install-knowledge-backfill.md]

- Affects: a future prod/webhook hardening phase — the composition root gates the whole sync chain on *all* of `github_app_id`, `github_app_private_key_path`, `mirror_root`, `github_org_logins` being present, and on partial/missing config merely logs a warning and leaves sync disabled (Assumption "gated, not hard-asserting"). This deliberately trades the `RepoMirror` docstring's intended fail-loud boot assertion for fail-quiet. It is the right call for keeping `/health`-only dev runs and the webhook-contract tests bootable today, but with "Logging: minimal" an operator could miss that a misconfigured production deployment silently never syncs. Worth a louder signal (or a health/readiness reflection of `knowledge_sync` state) when the webhook actually goes to production. [dismissed]

- Affects: a future throughput/hardening phase — `on_push` runs as an async FastAPI `BackgroundTask`, but `RepoMirror`'s git operations are blocking `subprocess.run` calls executed on the event loop. The HTTP ack is genuinely fast (the response is sent before the background task runs), but a `git fetch` inside `on_push` will stall the worker's event loop for concurrent requests during that window. Acceptable for the current single-tenant slice; revisit (offload to a thread/executor) when webhook concurrency matters. [routed → .ai-factory/specs/61-repo-mirror-async-boundary.md]

PLAN_REVIEW_PASS
