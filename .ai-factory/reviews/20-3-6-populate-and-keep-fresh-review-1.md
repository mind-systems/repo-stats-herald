# Code Review: 3.6 — Populate and keep fresh (impl)

**Reviewed:** `git diff HEAD` on branch `dev` — `src/core/config.py`, `.env.example`, `src/github/mirror.py`, `src/knowledge/sync.py` (new), `src/main.py`, `src/ingestion/router.py`, `scripts/backfill.py` (new), against the governing spec `.ai-factory/specs/08-populate-and-refresh.md` and every collaborator the change wires (`RepoMirror`, `ArtifactIndexer`, `AiFactorySourceStrategy`, `PgVectorStore`, `OllamaEmbedder`, `GitHubAppAuth`, `PushEvent`, the webhook router, the webhook-contract test suite).

Overall the implementation matches the plan and the spec: canonical-ref gating is checked before any tree is opened, `remove` is correctly gated on `strategy.selects` while `index` self-gates, the composition root is gated so `/health`-only runs and the lifespan-less contract tests still boot, and `background_tasks.add_task` fires correctly on a directly-returned `Response` (FastAPI assigns the collected `BackgroundTasks` to `response.background` when it is `None`).

Findings below, most severe first.

---

## Finding 1 — HIGH: empty `.env` values for the new `dict` settings crash `Settings()` on boot

**Files:** `src/core/config.py:23-24`, `.env.example:20-27`

`canonical_refs: dict[str, str] = {}` and `github_org_logins: dict[int, str] = {}` are plain complex-typed settings with no `NoDecode`/validator. pydantic-settings JSON-decodes complex fields from env, and an **empty string is not valid JSON**, so a *present-but-empty* env var for either field raises `SettingsError` before the app can construct `Settings`.

The regression is baked into the template this project tells developers to copy: `.env.example` ships

```
CANONICAL_REFS=
GITHUB_ORG_LOGINS=
```

The standard `cp .env.example .env` workflow therefore produces a `.env` that makes **every** entrypoint fail at startup — `make run`, `make dev`, `python -m scripts.backfill`, and the FastAPI app itself (including `GET /health`).

Verified empirically:

```
$ printf 'GITHUB_WEBHOOK_SECRET=x\nGITHUB_ORG_LOGINS=\nCANONICAL_REFS=\n' > /tmp/test.env
$ python -c "from src.core.config import Settings; Settings(_env_file='/tmp/test.env')"
SettingsError: error parsing value for field "canonical_refs" from source "DotEnvSettingsSource"
```

The existing test suite passes only because no `.env` exists in CI (it is git-ignored) and the fields fall back to `{}` — this hides the break from CI while breaking real local/prod boots.

Contrast `serve_allowlist`, which the same file deliberately guards with `Annotated[frozenset[int], NoDecode]` + a validator precisely so `SERVE_ALLOWLIST=` (empty) is tolerated. The new dicts need equivalent treatment.

**Fix (pick one):**
- Give both fields `NoDecode` + a `mode="before"` validator that treats `""`/`None` as `{}` and otherwise `json.loads` (mirrors the `serve_allowlist` pattern), **or**
- Remove the two empty `KEY=` lines from `.env.example` and document them as commented examples only (`# CANONICAL_REFS={"repo":"main"}`), so copying the template does not emit empty values.

The validator route is safer — it survives an operator leaving an empty value in any future `.env`.

---

## Finding 2 — MEDIUM: `backfill` crashes on a binary file under `docs/`

**Files:** `src/knowledge/sync.py:44-48`, `src/knowledge/indexer.py:36`, `src/knowledge/source_strategy.py:40`

`backfill` walks the **entire** canonical tree and calls `indexer.index(repo, path, tree)` for every file. `AiFactorySourceStrategy.selects` returns `True` for anything under `docs/` (`_PREFIXES = (".ai-factory/specs/", "docs/")` + `startswith`), and `ArtifactIndexer.index` reads the selected path with `(tree / path).read_text(encoding="utf-8")` unconditionally.

A served repo with any binary asset under `docs/` — `docs/img/diagram.png`, an architecture PDF, etc. — raises `UnicodeDecodeError`, which is not caught anywhere in `backfill`, aborting the whole run (and leaving the store partially populated depending on walk order).

`backfill` is the first consumer to feed an entire tree through the indexer, so this latent gap in the strategy/indexer surfaces here and fatally. This repo's own `docs/` is markdown-only today, so it will not reproduce locally — but any real org repo with a diagram or PDF under `docs/` breaks.

**Root cause** is the `docs/**`-selects-everything rule plus the unconditional `read_text`, both outside this task's changed files. Options: skip non-UTF-8 files (catch `UnicodeDecodeError` in the indexer and log-skip), or tighten the strategy to text/markdown extensions. At minimum this should be tracked as a follow-up against the 3.4 boundary; the 3.6 implementer should not assume backfill is safe on arbitrary served repos.

---

## Finding 3 — LOW: `clone_source` `KeyError` for a served org missing from `github_org_logins`

**Files:** `src/main.py:39-40`, `scripts/backfill.py:44-45`

The composition-root gate only checks that `github_org_logins` is **non-empty**, not that it contains the org being processed. `clone_source` does `settings.github_org_logins[org_id]`, so a served org that is in `SERVE_ALLOWLIST` but absent from the login map raises a bare `KeyError` deep inside `RepoMirror.ensure` — as an unhandled exception in the `on_push` background task (surfaced only in server logs), or a raw traceback from `scripts/backfill.py`, rather than a clear "org N has no configured login" message. Minor, but a `.get` with an explicit `LookupError`/log would fail more legibly.

---

## Finding 4 — LOW (deferred, already noted in plan): blocking git ops on the event loop

**File:** `src/knowledge/sync.py:39,43,54,74`

`RepoMirror.ensure`, `.tree`, and `.default_branch` are blocking `subprocess.run` calls, and `on_push` runs them inside a FastAPI `BackgroundTask` on the event loop. The HTTP ack is genuinely fast (response is sent before the task runs), but a `git fetch` will stall the worker's loop for concurrent requests during that window. Also note `ensure` (a network fetch, or a full clone on first sight) runs for **every** push including non-canonical ones, before the branch gate — intended per the "mirror pulled on each push" design, but worth being explicit about. Acceptable for the single-tenant slice; revisit with a thread/executor offload when webhook concurrency matters.

---

## Nit

- `KnowledgeSync._canonical_ref(self, repo, org_id)` accepts `org_id` but never uses it (`default_branch` needs only `repo`). Harmless; drop the param or keep for symmetry.

---

Finding 1 should be fixed before this ships — it breaks the documented setup path for every entrypoint. Findings 2–4 are correctness/robustness risks to schedule; none block the happy path on this repo.
