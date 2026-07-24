# 3.5 — Installation-repositories tracking

**Phase:** 3 — Repo mirror & semantic memory. Depends on 2.1 (webhook receipt + HMAC), 2.2 (serve-allowlist), and 3.3 (the asyncpg pool for its durable set).

## Current state

Task 2.1 (spec 01) branches on `X-GitHub-Event`: `push` is parsed, everything else → `204`. `docs/behavior/ingestion.md` ("Onboarding by installation") says Herald tracks the `installation_repositories` event so it learns immediately when a repository is added to or removed from its reach under an "Only select repositories" install — but no handler exists; that event is currently swallowed by the generic non-push `204`. This task sits in Phase 3, not Phase 2 — it needs a durable store for the served-repo set, and Postgres is only provisioned by 3.3.

## Change

Handle `installation` and `installation_repositories` events for served organizations, maintaining a durable set of repositories Herald currently reaches.

- A `served_repos` table (`org_id bigint`, `repo text`, `PRIMARY KEY (org_id, repo)`) on 3.3's asyncpg pool (`src/core/db.py`).
- In `src/ingestion/router.py`: recognize `X-GitHub-Event: installation` and `installation_repositories` (verified via the same HMAC check as 2.1, before parsing).
- Gate on the serve-allowlist (2.2) — only a served org's installation events are processed.
- Parse the event's `repositories_added`/`repositories_removed` (or the full repository list on `installation` create): added repos → `INSERT INTO served_repos ... ON CONFLICT DO NOTHING`; removed repos → `DELETE FROM served_repos WHERE ...`; `installation` create → seed the full repository list the same way.
- This task **maintains the set only** — it does not trigger a backfill. The newly-recorded repos are consumed by 3.6's "on install" backfill trigger, which runs later in build order.

## Files & types

- new migration for `served_repos` (alongside 3.3's schema)
- edit `src/ingestion/router.py` (handle `installation`/`installation_repositories`, upsert/delete against `served_repos`)
- possibly new `src/ingestion/models.py` addition (`InstallationEvent` or similar), if not already covered by 2.1's models

## Guards

- Only served orgs (2.2's allowlist) act on these events — an unlisted org's installation events are ignored, same discipline as its pushes.
- The push pipeline (2.1–2.2) is completely unaffected by this task.
- **Durable, idempotent set** — `INSERT ... ON CONFLICT DO NOTHING` / `DELETE` mean concurrent or replayed `installation_repositories` events for the same org need no explicit ordering; the set converges to the same state regardless of delivery order.
- Does not call backfill or any indexing — this task is earlier in build order than the pieces (3.6) that would consume the served-repo set.

## Verification

- An `installation_repositories` event with `repositories_added` for a served org → the added repo(s) recorded in the served-repo set.
- A `repositories_removed` event → the repo(s) removed from the set.
- The same event for an unlisted org → ignored, nothing recorded.
