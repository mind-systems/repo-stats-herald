## Plan Review — 2.2 Serve-allowlist gate

**Plan:** `.ai-factory/plans/11-2-2-serve-allowlist-gate.md`
**Governing spec:** `.ai-factory/specs/02-serve-allowlist-gate.md` (ROADMAP line 26)
**Files targeted:** `src/core/config.py`, `src/ingestion/router.py`, `tests/conftest.py`
**Risk Level:** 🔴 High

### Context Gates
- **Architecture** (`.ai-factory/ARCHITECTURE.md` / project CLAUDE.md): PASS. The plan keeps config-reading at the `Settings` seam and reads the allowlist through `settings` in the router — no inline env access, consistent with "Config is read once at the root and injected." No new cross-feature dependency introduced.
- **Rules** (`.ai-factory/RULES.md`): PASS. File is intentionally empty; no counter-defaults to check.
- **Roadmap** (ROADMAP.md line 26): PASS. Plan matches the contract line (add `Settings.serve_allowlist` as `frozenset[int]`, drop non-served org after parse with log+204, fail-closed, numeric org id) and links to the correct spec.

### Critical Issues

**1. Task 1's `frozenset[int]` field + `@field_validator(mode="before")` crashes on multi-id and empty-string env values — the exact fail-closed case the spec pins.**
`src/core/config.py` — pydantic-settings treats `frozenset[int]` as a *complex* field and JSON-decodes the raw env string **at the settings-source level, before any `mode="before"` validator runs**. The validator only ever sees a value if `json.loads` on the env string first succeeds. I verified this empirically against the project's pinned `pydantic-settings>=2.14.2`:

| `SERVE_ALLOWLIST` value | Result with the plan's approach |
|---|---|
| `244165546` (single, valid JSON number) | ✅ `frozenset({244165546})` |
| `244165546,244165547` (two orgs) | ❌ `SettingsError: error parsing value for field "serve_allowlist" from source "EnvSettingsSource"` |
| `` (empty string) | ❌ `SettingsError` |
| unset (field default) | ✅ `frozenset()` |

This directly contradicts the governing spec:
- Spec Guards line 13: *"empty string → empty set"* — the plan produces a `SettingsError` instead, so `get_settings()` raises and the webhook route 500s rather than dropping the push.
- Spec Verification line 33: *"With `SERVE_ALLOWLIST` empty → every push is dropped (fail-closed)."* — a crash is not "every push dropped"; the app fails to load settings.
- The moment a second served org is added to the comma-separated list (the whole point of the allowlist), production crashes at startup.

The trap is that the plan's own tests would go **green**: Task 3 sets `SERVE_ALLOWLIST=str(TEST_ORG_ID)` — a single integer, which is valid JSON and parses fine — and `Settings: Testing: no` means no case exercises the empty or multi-id path. So the defect ships silently behind passing tests.

**Fix:** disable pydantic-settings' complex-field JSON decode so the `mode="before"` validator owns the raw string. The minimal change that preserves the plan's intended field type:
```python
from typing import Annotated
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict, NoDecode

serve_allowlist: Annotated[frozenset[int], NoDecode] = frozenset()
```
I verified this variant yields `frozenset({244165546, 244165547})` for the two-org string, `frozenset()` for `""` and for a whitespace-only `" , "`, and `frozenset()` when unset — satisfying every spec case. Task 1 should be amended to require the `NoDecode` annotation (and note the `NoDecode` / `field_validator` imports); the rest of Task 1's validator description (pass sets through, split/strip/skip-empty/`int`) is correct and works once decode is disabled.

### Positive Notes
- **Router changes (Task 2) are accurate and correctly ordered.** The gate lands after `_parse_push_event` and after the existing non-`push`→204 short-circuit, so unverified/non-push requests never reach it. `event.org_id` (int) and `event.repo` both exist on `PushEvent`, and comparing the numeric `org_id` (not `org_login`) matches the spec's rename-proof guard.
- **The `settings = get_settings()` refactor is called out explicitly.** Line 53 currently reads `get_settings().github_webhook_secret` inline; the plan correctly instructs binding `settings` once and reading both fields from it, keeping the single-read discipline.
- **Task 3's test-fixture reasoning is correct.** Only `test_valid_signature_and_push_event_returns_populated_push_event` and `test_feature_branch_ref_is_stripped_to_branch_name` assert 200 and would regress to 204 under a fail-closed unset allowlist; the 401 (tampered/absent) and 204 (non-push) tests return before the gate and are unaffected. Setting `SERVE_ALLOWLIST=str(TEST_ORG_ID)` in `webhook_secret_env` (which already clears `get_settings.cache_clear()`) is the right seam.
- **`.env.example` claim verified** — the `SERVE_ALLOWLIST` key is already documented (lines 11–12), so "no change there" is correct.

Resolve Critical Issue 1 (add `NoDecode` to Task 1) and the plan is otherwise sound and spec-aligned.
