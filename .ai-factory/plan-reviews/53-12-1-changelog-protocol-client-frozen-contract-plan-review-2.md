## Plan Review Summary

**Plan:** 12.1 — Changelog protocol client + frozen contract
**Files the plan touches:** `contract/changelog.openapi.yaml` (new), `src/core/config.py`, `src/routing/models.py`, `src/routing/resolver.py`, `tests/routing/test_role_for_branch.py`, `src/delivery/changelog_client.py` (new), `tests/delivery/test_changelog_client.py` (new)
**Risk Level:** 🟢 Low

The plan is accurate against ground truth, and the sole finding from plan-review-1 — an untested resolver mapping — is now closed. Independent re-verification against the code:

- **config.py (Task 2):** `repo_apps` placement beside the sibling JSON-dict settings (`canonical_refs` line 37, `github_org_logins` 38, `telegram_channels` 39) and the `_parse_json_dict` `@field_validator` list at line 59 are cited correctly. `canonical_refs` really is `Annotated[dict[str, str], NoDecode]` parsed by that validator, so "mirrors `canonical_refs` exactly" holds — no new validator needed; passing a dict directly returns as-is, a JSON string goes through `json.loads`.
- **models.py (Task 3):** `DeliveryPlan` is `frozen=True, slots=True`; `telegram_channel` (line 16) is the first defaulted field and every field after it has a default, so inserting `changelog_base_url: str | None = None` alongside it keeps default-ordering valid and leaves existing construction sites (`resolver.py:22`, the delivery-service tests) compiling.
- **resolver.py (Task 3):** `DeliveryPlanResolver.resolve(org_id, repo, branch)` already receives `repo` (line 20), so `repo_apps.get(repo)` is a free lookup with no signature change. The bare-repo-vs-`org/repo` key invariant is real: the adjacent `telegram_channel` lookup keys on `org_id` (int) while `repo_apps` keys on the bare `repo` (str) — a swapped key would silently miss. Filling it unconditionally (not branch-gated) matches the resolver-seam design in `docs/behavior/delivery.md`.
- **Resolver test (Task 3):** now explicitly added, parallel to `test_resolve_maps_numeric_org_id_to_its_channel` / `test_resolve_returns_none_channel_for_unmapped_org` (`tests/routing/test_role_for_branch.py:43–59`), asserting `changelog_base_url` is filled from `repo_apps` by the bare repo and is `None` for an unmapped repo. This closes plan-review-1's Issue #1 within the task's own file boundary.
- **Client (Task 4):** scope matches the existing transport discipline (`telegram.py`, `github_release.py`): `httpx.AsyncClient` with an explicit `timeout` constructor arg (TelegramClient defaults `30.0`), `raise_for_status()`, no auth header. Keeping `ChangelogEntry.version` a plain `str` (caller passes `str(version)`) avoids importing `Version` into the delivery client, preserving the boundary.
- **Contract (Task 1):** the frozen fields — `version` string (`v`-prefixed example), `environment` enum `staging`/`production`, open `summaries` map (`additionalProperties: string`, no language fixed), `github_url` uri, `201` on entry — match `docs/behavior/delivery.md#internal-protocol` (Endpoints + field table) 1:1, and the two paths under `/internal/...` with no security scheme match the trust-boundary section. `contract/` does not yet exist; the plan correctly instructs creating it.
- **Stub tests (Task 5):** the referenced template (`tests/delivery/test_telegram_client.py`, monkeypatch of `httpx.AsyncClient`) exists; the plan correctly notes the new stub must route on method+URL, since the changelog client needs both GET and POST whereas the telegram fake is POST-only.

### Context Gates
- **Architecture (`.ai-factory/ARCHITECTURE.md`):** OK. `changelog` is a named natural feature boundary (line 15); the new client sits with the other delivery clients, depends on `httpx` transport + plan state (not another feature), and takes `base_url` per call holding no config — consistent with the composition-root wiring rule. A new top-level `contract/` directory is a reasonable cross-cutting artifact with no constraint against it.
- **Rules (`.ai-factory/RULES.md`):** OK — intentionally empty (no counter-defaults), so no rule to violate.
- **Roadmap / spec chain:** OK. `ROADMAP.md:117` (task 12.1) traces to `.ai-factory/specs/22-changelog-protocol-client.md`; every Change/Guard/Verification clause in that spec is represented across Tasks 1–5. The spec's stale `config.py:25,42-49` line refs are silently corrected to the real lines (37/59) in the plan — a correct deviation, not a defect. The downstream firing gate is correctly deferred to 12.2 (`ROADMAP.md:118`), keeping the resolver a pure unconditional lookup.

### Critical Issues
None.

### Positive Notes
- The mandatory 1/2/3-language `summaries` key-set test (Task 5) is a well-targeted guard — the one assertion that catches a hardcoded `{ru, en}` pair, which would pass every other check while dropping a third declared language. Good that it is explicit and non-optional.
- Task 3's added resolver test directly covers the plan's own emphasized silent-failure surface (bare-repo key vs int `org_id`), turning a prose invariant into a verified one.
- Pinning the changelog-firing gate to the caller (11.3/12.2) and keeping `changelog_base_url` filled unconditionally in the resolver keeps the seam a pure lookup, matching the resolver-state design so the config store can move to a database/GUI later without touching delivery code.

## Deferred observations
- Affects: operator configuration / `.env.example` — The new `REPO_APPS` env setting is not slated for an `.env.example` entry (plan sets `Docs: no`, and the file is outside this task's declared file boundary). Several JSON-dict settings there are documented (`CANONICAL_REFS`, `GITHUB_ORG_LOGINS`, `REPORT_SCHEDULES`), but its closest sibling `TELEGRAM_CHANNELS` is *not* documented there either, so the omission is consistent with existing precedent rather than a regression. Worth a one-line example when the delivery config surface is next revisited. [dismissed]

PLAN_REVIEW_PASS
