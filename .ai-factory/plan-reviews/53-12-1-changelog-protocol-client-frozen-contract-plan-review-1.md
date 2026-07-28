## Plan Review Summary

**Plan:** 12.1 — Changelog protocol client + frozen contract
**Files the plan touches:** `contract/changelog.openapi.yaml` (new), `src/core/config.py`, `src/routing/models.py`, `src/routing/resolver.py`, `src/delivery/changelog_client.py` (new), `tests/delivery/test_changelog_client.py` (new)
**Risk Level:** 🟢 Low

The plan is accurate against ground truth. Spot-checks that passed:
- `Settings.repo_apps` placement (config.py:37–39) and the `_parse_json_dict` validator field list (config.py:59) are cited correctly; `canonical_refs` really is a `dict[str, str]` with `NoDecode` parsed there, so the "mirrors `canonical_refs` exactly" instruction holds.
- `DeliveryPlanResolver.resolve(org_id, repo, branch)` already receives `repo`, so `repo_apps.get(repo)` is a free lookup with no signature change (resolver.py:20). The bare-repo-vs-`org/repo` key invariant matches how `telegram_channel` is keyed by `org_id` on the same line.
- `DeliveryPlan` is a `frozen, slots=True` dataclass; every field after `telegram_channel` has a default, so inserting `changelog_base_url: str | None = None` alongside it is valid and keeps `tests/delivery/test_delivery_service.py:16` and `resolver.py:22` construction sites compiling.
- The client scope matches the existing transport discipline (`telegram.py`, `github_release.py`): `httpx.AsyncClient` with an explicit timeout, `raise_for_status()`, no auth header. `version` kept as `str` on the wire (never importing `Version`) keeps the client decoupled, consistent with the caller passing `str(version)`.
- The frozen contract fields (`version`, `environment` enum `staging`/`production`, open `summaries` map, `github_url` uri) match `docs/behavior/delivery.md#internal-protocol` (lines 112–136) 1:1, including "no language fixed in the schema."
- The stub-test style referenced (`tests/delivery/test_telegram_client.py` monkeypatch-of-`httpx.AsyncClient`) exists and is the right template; the plan correctly notes the stub must "route on method+URL" (the changelog client needs both GET and POST, unlike the telegram POST-only fake).

### Context Gates
- **Architecture (`.ai-factory/ARCHITECTURE.md`):** OK. New `src/delivery/changelog_client.py` sits with the other delivery clients; feature depends on `httpx` transport + plan state, not on another feature. Client takes `base_url` per call and holds no config — consistent with the composition-root wiring rule. No boundary violation. A new top-level `contract/` directory is a reasonable cross-cutting artifact; ARCHITECTURE.md imposes no constraint against it.
- **Rules (`.ai-factory/RULES.md`):** OK — file is intentionally empty (no counter-defaults).
- **Roadmap / spec chain:** OK. Plan traces to `.ai-factory/specs/22-changelog-protocol-client.md`; every Change/Guard/Verification clause in that spec is represented in a task. The spec's own stale `config.py:25,42-49` line refs are silently corrected in the plan to the real lines — a correct deviation, not a defect.

### Critical Issues
None.

### Issues

**1. Resolver mapping (`changelog_base_url` from `repo_apps`) has no test — a silent-failure surface introduced by this task.** (`src/routing/resolver.py`, Task 3 / Task 5)
Task 3 adds `changelog_base_url = self._settings.repo_apps.get(repo)` to `resolve`, but the plan's test task (Task 5) covers only `ChangelogClient`. The spec's Verification section likewise lists only the stub tests, so an implementer following the plan literally would ship this mapping untested. This is exactly the surface the project's test-philosophy says to cover: it fails *silently*. The two adjacent lookups in `resolve` key on different arguments — `telegram_channel` by `org_id`, `changelog_base_url` by `repo` — and a swap to `repo_apps.get(org_id)` would always miss (str keys vs int) and quietly resolve `None`, deactivating the whole changelog channel with no error. The plan's own emphasized invariant ("bare `push.repo`, never `org/repo`") is precisely what would go unverified. The existing suite already tests the sibling mapping (`test_resolve_maps_numeric_org_id_to_its_channel`, `tests/routing/test_role_for_branch.py:43`); Task 3 should add a parallel resolver test asserting `changelog_base_url` is filled from `repo_apps` keyed by the bare repo and is `None` for an unmapped repo. This lands within the task's file boundary, so it is a finding rather than a deferred observation.

### Positive Notes
- The mandatory 1/2/3-language `summaries` key-set test (Task 5) is a well-targeted guard — it is the one assertion that catches a hardcoded `{ru, en}` pair, which would pass every other check while dropping a third declared language. Good that the plan makes it explicit and non-optional.
- Keeping `ChangelogEntry.version` a plain `str` and pushing `str(version)` to the caller avoids importing `Version` into the delivery client, preserving the model-agnostic boundary.
- The plan correctly forbids gating `changelog_base_url` on `branch_role` inside the resolver and pins the firing gate to the caller (11.3/12.2), keeping the resolver seam a pure lookup — this matches the resolver-state design in `docs/behavior/delivery.md`.

## Deferred observations
- Affects: operator configuration / `.env.example` — The new `REPO_APPS` env setting is not slated for an `.env.example` entry (plan sets `Docs: no`). Most JSON-dict settings there are documented (`CANONICAL_REFS`, `GITHUB_ORG_LOGINS`, `PROJECT_EDGES`, `REPORT_SCHEDULES`), but its closest sibling `TELEGRAM_CHANNELS` is *not* documented there either, so omission is consistent with existing precedent rather than a regression. Worth a one-line example when the delivery config surface is next revisited, but not required by this task. [dismissed]

Fix issue #1 (add the resolver test) and the plan is ready to implement.
