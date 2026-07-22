# Plan: 3.5 — Installation-repositories tracking

## Context
Teach the webhook receiver to handle GitHub `installation` / `installation_repositories` events (today swallowed by the non-`push`→204 branch) so Herald keeps a durable, idempotent `served_repos` set of the repositories it currently reaches — maintained only, consumed later by 3.6's on-install backfill.

## Settings
- Testing: no
- Logging: minimal
- Docs: no

## Pinned decisions (resolve fantasy holes before implementing)

- **Org identity comes from `installation.account.id`, not `organization.id`.** Push events carry `organization.id`; `installation`/`installation_repositories` events carry the org under `installation.account.id` (confirmed by `docs/spec/ingestion.md` "Who Herald serves"). Parse org id from `payload["installation"]["account"]["id"]`.
- **`served_repos.repo` stores the short repo name** (GitHub payload `repository.name` / `repositories[*].name`), matching `PushEvent.repo` (`repository["name"]` in `_parse_push_event`) and `RepoMirror`, which keys the bare store by the short name (`{mirror_root}/{repo}.git`). Do **not** store `full_name`.
- **Only `installation` with `action == "created"` mutates the set** — seed it with the payload's `repositories` list (the covered repos at install time). Every other `installation` action (`deleted`, `suspend`, `unsuspend`, `new_permissions_accepted`, …) is recognized and returns a 2xx but performs no set change. The spec scopes this task to "seed the full list on `installation` create" and "maintains the set only"; it does not define uninstall-purge behavior, so do not invent a purge-on-delete.
- **`ServedRepoStore` is a single concrete class — no ABC.** No second backend is imminent; per `ARCHITECTURE.md` principle 4 ("introduce an ABC when a real second implementation is imminent — not speculatively"), do not add an abstract base. This differs from `KnowledgeStore`/`PgVectorStore`, which had a red-test contract driving the ABC.
- **Success status is `204 No Content`.** Installation events have no meaningful response body; an unlisted org also returns `204` (same discipline as an unlisted push).
- **Missing keys default to empty.** `repositories_added` / `repositories_removed` / `repositories` may be absent — treat as `[]`, never `KeyError`.

## Tasks

### Phase 1: Persistence

- [x] **Task 1: Add the `served_repos` schema**
  Files: `src/ingestion/schema.sql`
  New file, following the `src/knowledge/schema.sql` pattern (idempotent DDL applied at a composition root). Contents:
  ```sql
  CREATE TABLE IF NOT EXISTS served_repos (
      org_id bigint NOT NULL,
      repo   text   NOT NULL,
      PRIMARY KEY (org_id, repo)
  );
  ```
  `bigint` because GitHub account ids exceed 32-bit range. The composite PK is what makes the upsert idempotent (Task 2).

- [x] **Task 2: Add `ServedRepoStore`** (depends on Task 1)
  Files: `src/ingestion/served_repos.py`
  A concrete class holding an injected `asyncpg.Pool` (mirror `PgVectorStore.__init__(self, pool: asyncpg.Pool)` in `src/knowledge/store.py`). SQL lives inside the class — never inline in the router. Two async methods:
  - `async def add(self, org_id: int, repos: Iterable[str]) -> None` — `INSERT INTO served_repos (org_id, repo) VALUES ($1, $2) ON CONFLICT DO NOTHING`, one row per repo (`executemany` over the acquired connection). No-op when `repos` is empty. Used for both `repositories_added` and the `installation` create seed.
  - `async def remove(self, org_id: int, repos: Iterable[str]) -> None` — `DELETE FROM served_repos WHERE org_id = $1 AND repo = ANY($2::text[])` (single statement over the list), no-op when empty.
  Both are idempotent by construction, so concurrent/replayed events for one org need no ordering (spec guard: durable, idempotent set).

### Phase 2: Event handling

- [x] **Task 3: Add the `InstallationEvent` model** (depends on nothing)
  Files: `src/ingestion/models.py`
  Add a frozen slotted dataclass alongside `PushEvent`, matching the existing style:
  ```python
  @dataclass(frozen=True, slots=True)
  class InstallationEvent:
      org_id: int
      repos_added: tuple[str, ...]
      repos_removed: tuple[str, ...]
  ```
  This is the normalized shape both event names parse into; the seed case fills `repos_added` with the full covered list.

- [x] **Task 4: Parse and dispatch installation events in the router** (depends on Task 2, Task 3)
  Files: `src/ingestion/router.py`
  - Add `_parse_installation_event(event_name: str, body: bytes) -> InstallationEvent` mirroring `_parse_push_event`'s structure (module-level `json.loads`, tuple comprehensions). Extract `org_id = payload["installation"]["account"]["id"]`. Then:
    - `event_name == "installation_repositories"` → `repos_added` from `payload.get("repositories_added", [])` (each `r["name"]`), `repos_removed` from `payload.get("repositories_removed", [])`.
    - `event_name == "installation"` and `payload.get("action") == "created"` → `repos_added` from `payload.get("repositories", [])` (the seed), `repos_removed` empty.
    - `event_name == "installation"` with any other action → both tuples empty.
  - **Restructure the event dispatch — this is the crux, and the trap.** Today `receive_github_webhook` (router.py:60‑61) short-circuits with an *early* `if request.headers.get("X-GitHub-Event") != "push": return Response(status_code=204)`. That exact line is what currently swallows installation events, so it **must not survive as-is** — do not read "the push pipeline is unaffected" as "leave this function's control flow alone." Convert it into per-event dispatch: read `event_name = request.headers.get("X-GitHub-Event")` once, then:
    - `event_name == "push"` → run the **existing push handling verbatim** (parse `PushEvent`, allowlist gate, return the `JSONResponse`) — the push *logic* is unchanged; only the guard that used to reject non-push before it is removed.
    - `event_name in ("installation", "installation_repositories")` → the new branch below.
    - anything else → the generic tail `return Response(status_code=204)`.
    Removing the early non-push return is precisely what makes installation events reachable; keeping it produces a silently non-functional feature (the bug this task exists to fix). The push guard's behavior (non-push with no other match still yields `204`) is preserved by the generic tail.
  - The installation branch:
    - Parse the `InstallationEvent`.
    - Gate on the allowlist exactly as push does — `if event.org_id not in settings.serve_allowlist:` log at info (`"org not served: org_id=%s"`) and `return Response(status_code=204)`, before any DB write.
    - Otherwise fetch the store from `request.app.state.served_repo_store` (wired in Task 5), then `await store.add(event.org_id, event.repos_added)` and `await store.remove(event.org_id, event.repos_removed)` (each is a no-op when its tuple is empty). Log the counts at info. `return Response(status_code=204)`.
  - Spec guard "push pipeline unaffected" means the push *behavior* (its parse, gate, and response) is byte-for-byte the same for a push request — not that this function's dispatch structure is frozen.

### Phase 3: Composition-root wiring

- [x] **Task 5: Create the pool and wire `ServedRepoStore` at the app root** (depends on Task 1, Task 2, Task 4)
  Files: `src/main.py`
  The router now depends on a pool that nothing currently creates. Add a FastAPI `lifespan` (async context manager passed as `FastAPI(lifespan=...)`) that wires concretes only here (per `ARCHITECTURE.md`: concretes chosen only at the composition root):
  - On startup: `settings = get_settings()`; `pool = await create_pool(settings.postgres_dsn)` (from `src/core/db.py`); read and `await conn.execute(...)` the `src/ingestion/schema.sql` text on one acquired connection (idempotent `CREATE TABLE IF NOT EXISTS`, resolve the path relative to this file like `tests/knowledge/conftest.py` does); `app.state.served_repo_store = ServedRepoStore(pool)`; keep the pool for shutdown.
  - On shutdown: `await pool.close()`.
  - Keep `GET /health` and `app.include_router(ingestion_router)` as-is.
  Note the existing webhook test suite builds `TestClient(app)` without entering it as a context manager, so lifespan does not run there and the push tests keep working without Postgres — the store is only touched on the installation branch, which those tests never exercise. Do not change that behavior.
