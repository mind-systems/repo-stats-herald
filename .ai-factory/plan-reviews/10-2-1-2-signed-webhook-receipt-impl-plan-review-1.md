## Code Review Summary

**Artifact reviewed:** `.ai-factory/plans/10-2-1-2-signed-webhook-receipt-impl.md` (plan)
**Files targeted:** `src/ingestion/router.py` (edit), verified against `src/ingestion/models.py`, `src/core/config.py`, `src/main.py`, `tests/conftest.py`, `tests/ingestion/test_webhook_contract.py`
**Risk Level:** 🟢 Low

### Context Gates

- **Roadmap alignment — OK.** Plan heading `2.1.2 — Signed webhook receipt (impl)` maps to `ROADMAP.md` line 25 and to its named spec `.ai-factory/specs/01-signed-webhook-receipt.md`. The plan's three implementation tasks (verify-before-parse, event-type gate, payload→`PushEvent`) match the spec's four-step Change list and every Guard (raw body, `hmac.compare_digest`, non-`push`→204, secret from env via `Settings`, no new test surface).
- **Architecture (`.ai-factory/ARCHITECTURE.md`) — WARN (non-blocking, justified).** The Dependency Rules prefer config read once at the composition root and injected, with features not reading env directly. The plan has the route handler call `get_settings().github_webhook_secret` at request time rather than receiving an injected primitive. This is the **correct** choice here and not a defect: the binding 2.1.1 test contract requires request-time resolution — `webhook_secret_env` in `tests/conftest.py` monkeypatches the env and calls `get_settings.cache_clear()` **per test** against a module-level `app`, so a value captured at app-construction time would not pick up the per-test secret. Reading via `Settings`/`get_settings()` (not raw `os.environ`) also satisfies the spec guard "secret only from env via `Settings`." No action required; flagged only for traceability.
- **Rules (`.ai-factory/RULES.md`) — OK.** File is intentionally empty (no project counter-defaults); nothing to check.
- **Skill-context (`aif-review/SKILL.md`) — not present.** No project-specific review overrides.

### Critical Issues

None.

### Correctness notes (verified, no action needed)

- **Header-absent path is safe.** Task 1 orders the guard as "header absent **or** `compare_digest` false", so short-circuit evaluation avoids passing `None` into `hmac.compare_digest` (which would raise). `test_absent_signature_is_rejected` passes only if the implementer preserves this order — the plan states it explicitly.
- **401 body is empty.** `test_tampered_signature_is_rejected` asserts `"branch" not in response.text`; the plan returns `Response(status_code=401)` with no body on both mismatch and absence. Correct.
- **Mapping matches the fixture and assertions.** `id`→`sha`, `author.name`→`author`, `removeprefix("refs/heads/")` (yields `main` / `feature/x`), int `org_id` from `organization.id`, tuples for `added/modified/removed/commits` — all line up with `push_payload` in `conftest.py` and the assertions in `test_valid_signature_and_push_event_returns_populated_push_event` / `test_feature_branch_ref_is_stripped_to_branch_name`.
- **Serialization is sound.** `JSONResponse(content=jsonable_encoder(event))` correctly serializes the frozen, slotted `PushEvent`/`PushCommit` dataclasses (FastAPI's `jsonable_encoder` handles dataclasses; tuples → JSON arrays), so `response.json()["commits"][0]["added"] == ["src/new_file.py"]` and `removed == []` hold. Returning a `Response` subclass under the existing `-> Response` annotation passes through FastAPI without re-validation.
- **No migration / no new config.** `Settings.github_webhook_secret` already exists (added by 2.1.1); the plan adds no schema, table, or env surface. Correct — nothing to migrate.
- **File scope respected.** All logic stays in `router.py`; the plan explicitly declines to add a new module, matching the spec's single-file scope. Optional `_verify_signature` / `_parse_push_event` helpers are module-private and in-file — fine.

### Positive Notes

- Verify-before-parse ordering is stated unambiguously and repeated across Tasks 1–3, directly encoding the security guard that is the point of this task.
- The plan pre-empts the two easy-to-miss trap points that would otherwise fail tests silently: the constant-time comparison (`compare_digest`, never `==`) and the empty 401 body.
- Grounds every mapping decision in the actual `push_payload` fixture rather than in a guessed GitHub schema, including the `id`→`sha` and nested-author renames.
- Phase 2 closes the loop by running the exact contract suite and enumerating the five expected outcomes.

PLAN_REVIEW_PASS
