## Plan Review — 2.2 Serve-allowlist gate (round 2)

**Plan:** `.ai-factory/plans/11-2-2-serve-allowlist-gate.md`
**Governing spec:** `.ai-factory/specs/02-serve-allowlist-gate.md` (ROADMAP line 26)
**Files targeted:** `src/core/config.py`, `src/ingestion/router.py`, `tests/conftest.py`
**Risk Level:** 🟢 Low

### Context Gates
- **Architecture** (`.ai-factory/ARCHITECTURE.md` / project CLAUDE.md): PASS. Config-reading stays at the `Settings` seam; the router reads the allowlist through `settings`, never inline env — consistent with "Config is read once at the root and injected." No new cross-feature dependency (ingestion → core only).
- **Rules** (`.ai-factory/RULES.md`): PASS. File is intentionally empty (no counter-defaults); nothing to check.
- **Roadmap** (ROADMAP.md line 26): PASS. Plan matches the contract line verbatim — `Settings.serve_allowlist` as `frozenset[int]`, drop `org_id not in allowlist` after parse (log + 204, no token/processing), fail-closed empty set, numeric-id comparison — and links the correct spec. Spec Verification bullets (served `244165546` proceeds; unlisted → 204; empty → all dropped) are all satisfied by the described behavior.

### Round-1 issue — resolved
Plan-review-1's sole Critical Issue was that a bare `frozenset[int]` field with a `mode="before"` validator crashes (`SettingsError`) on a comma-separated multi-id value and on an empty string, because pydantic-settings JSON-decodes complex fields at the source level before the validator runs — contradicting the spec's fail-closed empty-string case. **Task 1 now requires `serve_allowlist: Annotated[frozenset[int], NoDecode] = frozenset()`**, names the `NoDecode` / `Annotated` / `field_validator` imports, and explains exactly why the marker is needed. `NoDecode` is exported by `pydantic-settings>=2.14.2` (pinned in `pyproject.toml`), so the import resolves. The validator contract (pass sets/frozensets through; else split on `,`, strip, skip-empty, `int`; empty/whitespace → `frozenset()`) yields the spec's fail-closed set for every case. Issue closed.

### Critical Issues
None.

### Positive Notes
- **Task 1 is now precise and self-justifying.** It pins the field type, the required `NoDecode` marker, the exact imports (including adding `NoDecode` to the existing `from pydantic_settings import ...` line), and the validator's pass-through-then-parse contract. The `.env.example` claim is accurate — `SERVE_ALLOWLIST` is documented on lines 11–12, so "no change there" holds.
- **Task 2 lands the gate in the correct order.** It sits after `_parse_push_event(body)` (line 61) and after the non-`push` → 204 short-circuit (line 58–59), so unsigned/tampered (401) and non-push (204) requests never reach it. `event.org_id` (int) and `event.repo` both exist on `PushEvent` (`src/ingestion/models.py`), and comparing the numeric `org_id` — not `org_login` — matches the rename-proof guard. The instruction to bind `settings = get_settings()` once and read both `github_webhook_secret` and `serve_allowlist` from it correctly refactors the current inline `get_settings().github_webhook_secret` (line 53) while preserving the single-read discipline.
- **Task 3's fixture reasoning is verified against the tests.** Only `test_valid_signature_and_push_event_returns_populated_push_event` and `test_feature_branch_ref_is_stripped_to_branch_name` assert 200 (lines 25, 55) and would regress to 204 under a fail-closed unset allowlist; the two 401 tests and the 204 non-push test return before the gate and are unaffected. Setting `SERVE_ALLOWLIST=str(TEST_ORG_ID)` (`244165546`) in `webhook_secret_env` — which already `cache_clear()`s `get_settings` — is the right seam, and the id matches the payload the fixture builds (`organization.id = TEST_ORG_ID`).
- **Coverage tradeoff is consistent with the declared settings.** `Settings: Testing: no` means the plan adds no new test cases; Task 3 only re-wires the existing fixture to keep the served-org path green. The unlisted-org → 204 drop path is therefore exercised only indirectly. This is an acceptable consequence of the deliberate `Testing: no` setting rather than a plan defect — and note that the most likely silent regression (inverting the check to `in`) would break the existing 200 contract tests, since the served test org is on the allowlist.

The round-1 Critical Issue is fully addressed and no new issues surfaced. The plan is spec-aligned, correctly ordered, and grounded in the actual code.

PLAN_REVIEW_PASS
