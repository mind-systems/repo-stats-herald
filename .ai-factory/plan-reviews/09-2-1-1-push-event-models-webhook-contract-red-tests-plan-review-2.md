## Code Review Summary

**Files Reviewed:** 1 plan (`plans/09-2-1-1-push-event-models-webhook-contract-red-tests.md`) + supporting context (governing spec `specs/40-push-event-models-webhook-contract.md`, ingestion behavioral spec `docs/spec/ingestion.md`, prior `plan-review-1`, `src/commits/models.py`, `src/core/config.py`, `src/main.py`, `scripts/eval.py`, `scripts/summarize_range.py`, `Makefile`, `pyproject.toml`, `.env.example`, `.env.dev`, `.gitignore`, `.ai-factory/ARCHITECTURE.md`, `.ai-factory/RULES.md`)
**Risk Level:** 🟢 Low — the revised plan resolves plan-review-1's single critical issue and every claim it makes about the codebase checks out against ground truth.

### Context Gates
- **Architecture (`.ai-factory/ARCHITECTURE.md`)** — ✅ Aligned. `src/ingestion/` is a new self-contained feature package that owns its models + a *thin* `router.py` (the module template at line 30 explicitly allows `router.py` per feature); wiring happens only at the composition root `src/main.py` (`app.include_router(...)`); `Settings` is extended in the `core/` infra module. No feature-to-feature imports. Matches the feature-modular + constructor-DI pattern and the "routers thin, logic in services" rule (lines 82, 95).
- **Rules (`.ai-factory/RULES.md`)** — ✅ Empty by design (no counter-defaults); nothing to violate.
- **Roadmap → spec (`specs/40-push-event-models-webhook-contract.md`)** — ✅ The plan is the governing spec's first ingestion task and covers every spec bullet: `PushCommit`/`PushEvent` field lists match the spec verbatim, `github_webhook_secret` required-no-default, stub `POST /webhooks/github` wired at the root, and red tests for valid→200 / tampered+absent→401 / non-push→204 / ref→branch strip / numeric `org_id`. The one narrowing — stub returns `501` rather than raising `NotImplementedError` — is explicitly permitted by the spec ("raises `NotImplementedError` (or returns `501`)", spec lines 15/33), and the plan's reasoning (a raised exception surfaces through `TestClient` as a re-raised 500 and muddies "failed for the right reason") is correct. A well-reasoned selection, not a deviation.

### Resolution of plan-review-1
The prior review raised one critical issue: `uv run pytest` does not put the project root on `sys.path`, so `from src.main import app` in `conftest.py` would raise `ModuleNotFoundError` at collection and every test would *error* rather than *fail red* — defeating the task's central guard.

This is now fully resolved and verified against ground truth:
- `pyproject.toml` still has no `[build-system]` (confirmed), so `src` is importable only with the root on `sys.path`.
- The `-m` run-form dependency is real: both `scripts/eval.py` and `scripts/summarize_range.py` document "Run as a module from the project root" (confirmed in their headers), which is what puts CWD on the path today.
- The revised plan mandates `pythonpath = ["."]` in `[tool.pytest.ini_options]` in **two** places — the implementer notes (line 14) and Task 5 (line 47) — and correctly labels it mandatory, not optional polish. This is declarative, survives a bare `pytest` invocation, and keeps the harness independent of the run form. `pythonpath` is a pytest ≥7 ini option and current `pytest` (8.x) supports it, so the unpinned `dev = ["pytest"]` is fine.

### Critical Issues
None.

### Positive Notes
- **Faithful, minimal type surface.** `PushCommit`/`PushEvent` copy the `@dataclass(frozen=True, slots=True)` + `tuple[...]` pattern from `src/commits/models.py` exactly, and the `org_id: int` vs `org_login: str` split is preserved *and* given teeth in the test (distinct numeric id `244165546` vs a login string).
- **Required-field boot-safety argument holds.** Importing `src.main` (FastAPI + logic-free router + model module) instantiates `Settings` nowhere, so a required `github_webhook_secret` introduces no import/boot regression on the web path; `.env.example` line 9 already documents the key. In this task nothing even reads `Settings` (the stub reads none), so `Settings` is never instantiated during the red run — cleaner still.
- **`.env.dev` carries the key** (confirmed: `GITHUB_WEBHOOK_SECRET` present), so making the field required introduces no regression for `make dev`/`make eval`, which instantiate `Settings` via `get_settings()`. The plan's deferred note (line 68) states this correctly and owes no `.env.dev` change.
- **Forward-looking conftest design.** Clearing `get_settings`'s `lru_cache` after `monkeypatch.setenv`, plus centralizing the secret constant and `sign()`/payload-builder helpers, sets up the seam 2.1.2 will read so the tests sign with exactly the secret 2.1.2 verifies against.
- **Runtime-dep claim holds.** `fastapi.testclient.TestClient` rides on `httpx` (already a dependency), so `pytest` is the only new dep; the `[dependency-groups] dev` + `uv sync` route is the correct modern (PEP 735) mechanism.
- **Payload shape matches GitHub + spec.** `organization.id`/`organization.login`, `repository.name`, `ref = "refs/heads/main"`, `before`/`after`, and a `commits` list mirror a real push and align with `docs/spec/ingestion.md` ("What the push carries") and the numeric-org-id serve-allowlist gate.

## Deferred observations
- Affects: task 2.1.2 (`specs/01-signed-webhook-receipt.md`) — The valid-signature test reads `branch`/`org_id`/commit fields from the HTTP **response body**, which binds 2.1.2 to echo the parsed `PushEvent` back in the `200` response. At this task's stage that echo is the only observable proof parsing worked, so it is a sound contract-test choice — but a production webhook receiver normally returns a minimal `200` and hands the event to a pipeline rather than serializing it. When the real downstream consumer lands, revisit whether the endpoint should still serialize the full event, or whether this observability hook should move to the pipeline seam, so the response shape is not frozen purely by a red test. (The plan itself flags this at line 67.)

PLAN_REVIEW_PASS
