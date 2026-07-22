## Plan Review — 3.5 Installation-repositories tracking

**Plan:** `.ai-factory/plans/19-3-5-installation-repositories-tracking.md`
**Files Reviewed (targets + reference chain):** plan, `src/ingestion/router.py`, `src/ingestion/models.py`, `src/main.py`, `src/core/db.py`, `src/core/config.py`, `src/knowledge/store.py`, `src/knowledge/schema.sql`, `src/github/mirror.py`, `tests/knowledge/conftest.py`, `tests/ingestion/test_webhook_contract.py`, `docs/spec/ingestion.md`, `.ai-factory/specs/36-installation-repositories-tracking.md`, `.ai-factory/ROADMAP.md`, `.ai-factory/ARCHITECTURE.md`, `.ai-factory/RULES.md`
**Risk Level:** 🟢 Low

### Context Gates
- **Architecture (`ARCHITECTURE.md`)** — OK. The plan honors every load-bearing principle: `ServedRepoStore` receives an injected `asyncpg.Pool` (principle 3, DI), concretes are wired only in `src/main.py`'s lifespan (principle 3/dependency rules), SQL stays inside the store class (principle 6, encapsulation), and the deliberate no-ABC decision is correctly justified against principle 4 ("introduce an ABC when a real second implementation is imminent — not speculatively"). The store lives inside the `ingestion` feature package, not a shared root — consistent with feature ownership.
- **Rules (`RULES.md`)** — OK. File is intentionally empty (no counter-defaults); nothing to check.
- **Roadmap (`ROADMAP.md` line 3.5 + spec `36-...`)** — OK, faithful. Contract line and task spec both call for: a `served_repos` table on 3.3's `create_pool`, HMAC verification (2.1) before parsing, serve-allowlist gating (2.2), `INSERT … ON CONFLICT DO NOTHING` on added / `DELETE` on removed / seed the full list on `installation` create, idempotent + order-free, "maintains the set only" (no backfill). Every one of these maps to a task. Downstream consumers (3.6 on-install backfill, 10.2 report iterating `served_repos`) are correctly left untouched.

### Grounding verification (claims checked against code)
- **Org identity `installation.account.id`** — confirmed by `docs/spec/ingestion.md` ("Who Herald serves": `organization.id` / `installation.account.id` are the same org identity). Push uses `payload["organization"]["id"]` (router.py:42); allowlist is `frozenset[int]` (config.py:19) populated from that same id namespace, so `installation.account.id` matches correctly. ✅
- **Short repo name, not `full_name`** — matches `_parse_push_event` (`payload["repository"]["name"]`, router.py:44) and `RepoMirror._bare_path` which keys the bare store by short name `{mirror_root}/{repo}.git` (mirror.py:53‑54). ✅
- **`bigint` for `org_id`** — correct; mirrors the reasoning that account ids exceed 32-bit. Table shape mirrors `knowledge/schema.sql`'s idempotent `CREATE TABLE IF NOT EXISTS` + composite PK pattern. ✅
- **`create_pool(settings.postgres_dsn)`** — signature matches: `create_pool(dsn: str)` (db.py:22) and `Settings.postgres_dsn` property (config.py:37‑42). ✅
- **Schema-load-relative-to-file pattern** — `tests/knowledge/conftest.py:11` uses `Path(__file__).resolve().parents[2] / …`; the plan's "resolve relative to this file" for `src/main.py` is the same idiom. ✅
- **GitHub payload shapes** — `installation_repositories` carries `repositories_added` / `repositories_removed` (lists of `{id,name,full_name,private}`); `installation` `created` carries `repositories`. `r["name"]` yields the short name in all three. `.get(..., [])` defaulting is the right guard against absent keys. ✅
- **Lifespan / test coexistence** — confirmed: `test_webhook_contract.py` drives push/ping only and never the installation branch, and `TestClient(app)` used without a `with` block means lifespan (hence `app.state.served_repo_store`) never runs — push tests keep passing without Postgres. ✅

### Critical Issues
None. No missing migration (Task 1 adds it), no wrong API usage, no security regression (HMAC stays first, allowlist gates before any DB write), no architectural violation.

### Issues

- **Task 4 — "leave the `push` path completely untouched" is a control-flow trap as worded.** Today `receive_github_webhook` (router.py:60‑61) short-circuits with an *early* `if request.headers.get("X-GitHub-Event") != "push": return Response(status_code=204)` — that line is exactly what currently swallows installation events. An implementer who takes "leave the push path completely untouched" literally and keeps that early-return will have every `installation`/`installation_repositories` request hit the `!= "push"` 204 *before* reaching the new branch, silently producing a non-functional feature (the very bug this task exists to fix). The plan's own phrases "the existing push branch" and "the final generic return … for all other event types" imply the correct restructure (read `event_name` once → handle `push` and return → handle installation and return → tail `204`), but the "completely untouched" instruction contradicts it. Recommend rewording Task 4 to state explicitly that the non-push early-return must be converted into per-event dispatch: the push *handling logic* is unchanged, but the guard that returns 204 for non-push must move to a generic tail so installation events are reachable.

### Positive Notes
- The **Pinned decisions** block is exemplary: it closes the exact fantasy holes an implementer would otherwise guess — org-id source, short-name vs full_name, which single action seeds, no speculative purge-on-delete, no speculative ABC, `204` discipline, and empty-key defaults — each grounded in a cited file. This is the difference between a plan that converges first try and one that loops.
- Idempotency is designed structurally (composite PK + `ON CONFLICT DO NOTHING` + set-based `DELETE`), so the spec's "concurrent/replayed events need no ordering" guard holds by construction rather than by runtime coordination.
- Security posture preserved: signature check stays first, allowlist gate returns `204` *before* any DB write, matching the push discipline exactly — an unlisted org triggers no work.
- Scope discipline is clean: "maintains the set only," no backfill, no purge-on-delete, downstream (3.6/10.2) untouched — the plan resists inventing behavior the spec does not define and says so explicitly.

## Deferred observations
- Affects: infra / future Phase-3 wiring — `src/core/db.py`'s `create_pool` unconditionally registers a `set_type_codec("vector", schema="public", …)` on every connection, so the pool Task 5 opens will fail to start unless the pgvector `vector` type exists in `herald_database`, even though `served_repos` uses no vector column and the app's lifespan applies only `src/ingestion/schema.sql` (which does not `CREATE EXTENSION vector`). In practice the extension is a one-time machine prerequisite documented in the project `CLAUDE.md` setup, and reusing the shared `create_pool` is the spec-mandated choice ("3.3's asyncpg pool"), so this is not a defect in the plan — but when 3.6 wires the knowledge store into the same app root it will also need the `chunks` schema (and the extension) applied at startup; the extension dependency is worth making explicit there rather than relying on manual setup.

The single issue above is a low-severity wording clarification, not a design flaw — but because it is a genuine implementation trap in the current task's boundary it is recorded as a finding rather than a pass.
