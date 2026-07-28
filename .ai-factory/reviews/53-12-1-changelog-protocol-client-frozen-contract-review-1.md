# Code Review: 12.1 — Changelog protocol client + frozen contract

**Scope reviewed:** `contract/changelog.openapi.yaml` (new), `src/core/config.py`, `src/routing/models.py`, `src/routing/resolver.py`, `src/delivery/changelog_client.py` (new), `tests/delivery/test_changelog_client.py` (new), `tests/routing/test_role_for_branch.py`.

## Verification performed
- Read every changed/new file in full against the plan and the frozen contract.
- Ran the two targeted test files: 17 passed.
- Ran the full suite: **196 passed** (no regressions from the `DeliveryPlan` field insertion or the shared `_parse_json_dict` validator change).
- Confirmed the JSON-string parse path for `repo_apps` produces **`str` keys** (`{'repo': ...}`, key type `str`) — the bare-repo key invariant holds, and unlike `telegram_channels` there is no int-coercion, which is correct for a `dict[str, str]`.

## Findings

**Correctness — contract ↔ client parity.** `ChangelogClient.entry` posts exactly `{version, environment, summaries, github_url}` and `.config` reads `["languages"]`; both endpoint paths (`/internal/changelog/config`, `/internal/changelog/entry`) and the request/response shapes match `contract/changelog.openapi.yaml` 1:1. `version` is carried through verbatim as a `str` (no `Version` import, no reformatting), preserving the model-agnostic boundary and the "same token everywhere" invariant.

**Transport discipline.** `httpx.AsyncClient` with an explicit timeout, `raise_for_status()` on both calls (errors raise, never a silent success), and no auth header — matching `telegram.py`/`github_release.py` and the internal-network trust boundary. Error-path tests assert the raise is not swallowed.

**Resolver seam.** `changelog_base_url` is filled unconditionally on every `resolve` from `repo_apps.get(repo)` — keyed by the bare `repo`, not `org_id` — sitting beside `telegram_channel` with no branch gating inside the resolver. The two added resolver tests cover both the mapped-bare-repo and unmapped-repo cases, closing the silent-failure surface flagged in plan-review round 1.

**Config.** `repo_apps` added to the existing `_parse_json_dict` validator field list (no new validator), mirroring `canonical_refs`. `DeliveryPlan.changelog_base_url: str | None = None` is defaulted, so all existing construction sites stay valid (confirmed by the green full suite).

**Tests.** The mandatory 1/2/3-language `summaries` key-set test is present and parametrized — it asserts the posted key set equals exactly the declared languages, catching a hardcoded `{ru, en}` pair. Stub asserts the body shape by hand, no schema-validator dependency added.

No bugs, security issues, or correctness problems found. Implementation matches the plan, the spec, and the frozen contract.

REVIEW_PASS
