# Plan: 3.6 — Populate and keep fresh

## Context
Adds `KnowledgeSync` so a served repo's knowledge store is populated on first sight (`backfill`) and kept current on every **canonical-ref** push (`on_push`) — a non-canonical push touches no semantic memory — closing Phase 3. This is also the first place the `RepoMirror`/`ArtifactIndexer` chain is wired into a live composition root.

## Settings
- Testing: no
- Logging: minimal
- Docs: no

## Assumptions & key decisions
- **Canonical-ref resolution.** `Settings.canonical_refs` holds optional per-repo overrides (`repo → branch`). When a repo has no override, the canonical ref is the repo's **default branch**, read from the mirror's bare `HEAD` (`git symbolic-ref --short HEAD`) — hence the new `RepoMirror.default_branch`. Git-command details stay inside `RepoMirror` (encapsulation), so `KnowledgeSync` never shells git itself.
- **Changed-path handling in `on_push` is state-at-`push.after`, not raw add/modify/remove sets.** For each path in the union of every commit's `added ∪ modified ∪ removed`, decide by its presence in the tree at `push.after`: present → `ArtifactIndexer.index` (self-gates on `SourceStrategy.selects`); absent → `ArtifactIndexer.remove` (gated on `selects` so a code-only push does no store work). This faithfully realizes the spec's "index the added/modified, remove the deleted" while correctly resolving a path that was modified in one commit and deleted in a later one of the same push.
- **Mirror clone URL needs the org login, which the fixed `clone_source(repo, org_id)` signature (3.1.2) does not carry.** Added `Settings.github_org_logins` (`org_id → login`); the composition root builds `clone_source` from it. Minimal and config-driven; generalizes to multi-org later.
- **Composition root is gated, not hard-asserting.** `main.py` builds the sync chain only when the GitHub-App + mirror + org-login settings are present; otherwise it logs that sync is disabled and leaves `app.state.knowledge_sync` unset. This keeps `/health`-only dev runs and the existing webhook-contract tests (which construct `TestClient(app)` without running `lifespan`) bootable without full GitHub-App credentials. The router skips `on_push` when `knowledge_sync` is absent.
- **`on_push` runs as a FastAPI background task** so the webhook acks fast (it does a git fetch + embeddings). The push response body stays the JSON-encoded `PushEvent` to preserve the 2.1.x webhook contract.
- **Scope beyond the spec's explicit file list.** Spec 08 lists `sync.py`/`config.py`/`router.py`, but its own prose requires wiring `on_push` into ingestion and a backfill entrypoint — which need composition-root changes (`main.py`), the `default_branch` reader (`mirror.py`), and `scripts/backfill.py`. These are included to satisfy the spec's behavior.

## Tasks

### Phase 1: Configuration & mirror support

- [x] **Task 1: Extend `Settings` with canonical-ref policy + org-login map**
  Files: `src/core/config.py`, `.env.example`
  Add two fields to `Settings`: `canonical_refs: dict[str, str] = {}` (per-repo canonical-ref override; absent → the repo's default branch) and `github_org_logins: dict[int, str] = {}` (org id → GitHub login, used to build mirror clone URLs). Both are pydantic-native dicts parsed from env JSON — no custom validator needed. Document both keys in `.env.example` under the GitHub-App section (e.g. `CANONICAL_REFS={"repo-name":"main"}`, `GITHUB_ORG_LOGINS={"244165546":"mind-systems"}`), values empty by default.

- [x] **Task 2: Add `RepoMirror.default_branch` (and a startup worktree sweep)**
  Files: `src/github/mirror.py`
  Add `default_branch(self, repo: str) -> str`: run `git symbolic-ref --short HEAD` in the repo's bare object store (`self._bare_path(repo)`), capturing stdout (a small `subprocess.run(..., capture_output=True, text=True, check=True)` — keep the git detail here, mirroring `_run_git`), return the stripped branch name (e.g. `main`). The caller must have run `ensure` first so the bare clone exists. Also add a startup reclamation method (e.g. `sweep_worktrees()`) that removes every entry under `{mirror_root}/worktrees` and runs `git worktree prune` per bare repo — this realizes the disk-leak guard the class docstring assigns to "the consuming task" (worktrees finished right before a crash are never picked up by `ensure`). The composition root (Task 4) calls it once at startup.

### Phase 2: KnowledgeSync

- [x] **Task 3: Implement `KnowledgeSync`** (depends on Task 1, Task 2)
  Files: `src/knowledge/sync.py`
  New feature class in the `knowledge` package. Constructor DI (no concretes built here): `KnowledgeSync(mirror: RepoMirror, indexer: ArtifactIndexer, strategy: SourceStrategy, canonical_refs: dict[str, str])`.
  - `_canonical_ref(self, repo, org_id) -> str`: return `canonical_refs.get(repo)` if set, else `mirror.default_branch(repo)`.
  - `async def backfill(self, repo: str, org_id: int) -> None`: `mirror.ensure(repo, org_id)`; resolve the canonical ref; `with mirror.tree(repo, org_id, canonical) as tree:` walk every file under `tree` (skip any path whose parts contain `.git`; compute repo-relative POSIX path via `p.relative_to(tree).as_posix()`) and `await indexer.index(repo, path, tree)` for each — `ArtifactIndexer.index` self-gates on `SourceStrategy.selects`, so non-artifacts are no-ops. Idempotent by construction (`KnowledgeStore.upsert` is delete-then-insert per `(repo, path)`).
  - `async def on_push(self, push: PushEvent) -> None`: `mirror.ensure(push.repo, push.org_id)` (keeps the mirror fresh); resolve the canonical ref; **if `push.branch != canonical`, log at debug and return without opening a tree** (the semantic-memory-is-one-ref guard, checked before any tree is opened). Otherwise compute the changed-path set (union of `added ∪ modified ∪ removed` across `push.commits`), then `with mirror.tree(push.repo, push.org_id, push.after) as tree:` for each changed path: if `(tree / path).is_file()` → `await indexer.index(push.repo, path, tree)`; else if `strategy.selects(path)` → `await indexer.remove(push.repo, path)`.
  - Log one info line per backfill/on-push summarizing repo, ref, and counts; keep logging minimal.

### Phase 3: Wiring

- [x] **Task 4: Wire the sync chain into the web composition root** (depends on Task 3)
  Files: `src/main.py`
  In `lifespan`, after the pool is created: also apply `src/knowledge/schema.sql` (idempotent `CREATE ... IF NOT EXISTS`) so the `chunks` table exists. Then, **only when** `settings.github_app_id`, `settings.github_app_private_key_path`, `settings.mirror_root`, and `settings.github_org_logins` are all present, assemble the sync chain (concretes wired here only):
  - `embedder = OllamaEmbedder(settings.ollama_url, settings.embed_model, settings.ollama_api_key)`
  - `store = PgVectorStore(pool)`
  - `strategy = AiFactorySourceStrategy()`
  - `indexer = ArtifactIndexer(strategy, embedder, store)`
  - read the PEM text from `settings.github_app_private_key_path`; `auth = GitHubAppAuth(settings.github_app_id, pem)`
  - `clone_source = lambda repo, org_id: f"https://github.com/{settings.github_org_logins[org_id]}/{repo}.git"`
  - `mirror = RepoMirror(Path(settings.mirror_root), auth, clone_source)`; call `mirror.sweep_worktrees()` (Task 2) once here
  - `app.state.knowledge_sync = KnowledgeSync(mirror, indexer, strategy, settings.canonical_refs)`
  When the required settings are absent, log a warning that canonical-ref sync is disabled and leave `knowledge_sync` unset. Do not remove the existing `served_repo_store` wiring or the ingestion-schema application.

- [x] **Task 5: Invoke `on_push` from the webhook after the serve-allowlist** (depends on Task 4)
  Files: `src/ingestion/router.py`
  Add a `background_tasks: fastapi.BackgroundTasks` parameter to `receive_github_webhook`. In the `push` branch, after the org passes the serve-allowlist and before returning the event JSON, read `knowledge_sync = getattr(request.app.state, "knowledge_sync", None)`; if it is not `None`, `background_tasks.add_task(knowledge_sync.on_push, event)`. Keep the existing `JSONResponse(content=jsonable_encoder(event))` response (preserves the 2.1.x contract). The `getattr` guard keeps the existing webhook-contract tests green (they build `TestClient(app)` without running `lifespan`, so `knowledge_sync` is absent → `on_push` skipped).

- [x] **Task 6: Add the backfill entrypoint** (depends on Task 3)
  Files: `scripts/backfill.py`
  Composition-root script mirroring `scripts/summarize_range.py`: `argparse` for `--repo` and `--org-id`; build `Settings`, `create_pool(settings.postgres_dsn)`, apply `src/knowledge/schema.sql`, assemble the same concrete chain as Task 4 (`OllamaEmbedder`, `PgVectorStore`, `AiFactorySourceStrategy`, `ArtifactIndexer`, `GitHubAppAuth` from the PEM, `RepoMirror` with the `github_org_logins`-based `clone_source`, `KnowledgeSync`); `asyncio.run(sync.backfill(args.repo, args.org_id))`; close the pool in a `finally`. Assembly only — no logic beyond wiring and delegating. Document the invocation in the module docstring (`uv run python -m scripts.backfill --repo <name> --org-id <id>`).

## Verification (manual — no new tests)
- `uv run pytest` — the existing webhook-contract and mirror/knowledge suites stay green (the push path still returns 200 + the event; `on_push` is skipped when `knowledge_sync` is unset).
- With GitHub-App + Postgres + Ollama configured: `python -m scripts.backfill --repo <served-repo> --org-id <id>` populates the store from the canonical ref; a knowledge query returns relevant chunks.
- A served push to the canonical ref editing `ROADMAP.md` re-indexes only `ROADMAP.md`; adding `docs/spec/x.md` indexes it; deleting a doc clears its chunks.
- A served push to a non-canonical branch (e.g. `feature/x`) opens no tree and does no indexing; a canonical push touching only `src/*.py` opens a tree but does no store work.
