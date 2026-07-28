## Code Review Summary

**Files Reviewed:** 1 plan + supporting context (spec `40-push-event-models-webhook-contract.md`, ROADMAP lines 2.1.1/2.1.2, `src/commits/models.py`, `src/core/config.py`, `src/main.py`, `Makefile`, `pyproject.toml`, `.env.example`, `.gitignore`, `ARCHITECTURE.md`, `RULES.md`, `scripts/*.py`)
**Risk Level:** 🟡 Medium — the type/route/wiring/test design is sound and faithful to the spec, but the pytest-harness setup (Task 5) omits the one config the whole task's red-for-the-right-reason guard depends on. Fixable with a one-line addition.

### Context Gates
- **Architecture (`.ai-factory/ARCHITECTURE.md`)** — ✅ Aligned. New feature package `src/ingestion/` owns its models + thin router; router wired only at the composition root (`src/main.py`); `Settings` extended in `core/`; no feature-to-feature imports. Matches the feature-modular + DI pattern.
- **Rules (`.ai-factory/RULES.md`)** — ✅ Empty by design (no counter-defaults); nothing to violate.
- **Roadmap (`ROADMAP.md` line 24 → spec `specs/40-...md`)** — ✅ Task is the governing spec's first ingestion task; plan covers every spec bullet (models, `github_webhook_secret`, stub route, wiring, red tests for valid→200 / tampered+absent→401 / non-push→204 / ref→branch / numeric org_id). One intentional narrowing (stub returns `501` rather than raising) is **within the spec's stated allowance** — spec line 15/33 says "raises `NotImplementedError` (or returns `501`)". The plan's justification (a raised exception surfaces through `TestClient` as a re-raised 500 and muddies "failed for the right reason") is correct and is the better of the two spec-allowed options. Not a deviation — a well-reasoned selection.

### Critical Issues

**1. Task 5 — pytest cannot import `src.main` as planned; tests will error on collection (`ModuleNotFoundError: No module named 'src'`), not fail red for the right reason.**

This directly defeats the task's central guard ("The tests MUST fail against the stub — and fail for the right reason … never an import/fixture error").

Ground truth:
- `pyproject.toml` has **no `[build-system]`**, so the project is not installed as a package. `src` is importable only when the **project root is on `sys.path`**.
- The established mechanism for that in this repo is the `-m` run form: both `scripts/eval.py` and `scripts/summarize_range.py` document "Run as a module from the project root: `uv run python -m scripts.eval`". The `-m` form puts CWD (project root) on `sys.path`; that is how `from src.commits… import` resolves today.
- The plan runs pytest as `uv run pytest` (Makefile `test` target = `uv run pytest`) — the **console-script** form, which does **not** add CWD to `sys.path`.
- pytest's default (prepend) import mode inserts the *basedir of each test/conftest* onto `sys.path` — i.e. `tests/` (and possibly `tests/ingestion/`), **never the project root**. So when `tests/conftest.py` does `from src.main import app`, `src` is not resolvable.
- The plan's `[tool.pytest.ini_options]` block specifies only `testpaths` — no `pythonpath`, and no project-root `conftest.py` is planned.

Net effect: collection fails before any assertion runs; every test errors rather than failing red against the `501` stub. The verification bullet ("red … no import errors") would not be met.

Fix (pick one, add to Task 5):
- Add `pythonpath = ["."]` to `[tool.pytest.ini_options]` (pytest ≥7; cleanest, matches the src-not-installed layout), **or**
- add a project-root `conftest.py` (its presence puts the root on `sys.path`), **or**
- make the Makefile target `uv run python -m pytest` (mirrors how the scripts already run).

Recommend the `pythonpath = ["."]` option — it is declarative, survives direct `pytest` invocation, and keeps the harness independent of the run form.

### Positive Notes
- **Faithful, minimal type surface.** `PushCommit`/`PushEvent` field lists match the spec exactly, and the `@dataclass(frozen=True, slots=True)` + `tuple[...]` pattern is copied precisely from `src/commits/models.py`. `org_id: int` vs `org_login: str` split is preserved and given teeth in the test (distinct numeric id vs login).
- **Stub decision is well-reasoned** (see Roadmap gate) and keeps the red run clean.
- **Required-field boot-safety argument is correct for `make run`.** Importing `src.main` (FastAPI + the logic-free router + the model module) instantiates `Settings` nowhere, so a required `github_webhook_secret` introduces no import-time/boot regression on the web path. `.env.example` line 9 already documents the key, so no doc change is owed.
- **Forward-looking conftest design.** Clearing `get_settings`'s `lru_cache` after `monkeypatch.setenv`, and centralizing the secret constant + `sign()` helper, correctly sets up the seam 2.1.2 will read — the tests sign with exactly the secret 2.1.2 will verify against.
- **Runtime-dep claim holds.** FastAPI's `TestClient` rides on `httpx` (already a dependency), so `pytest` is the only new dep; the `[dependency-groups] dev` + `uv sync` route is the right modern mechanism.

## Deferred observations
- Affects: task 2.1.2 (`specs/01-signed-webhook-receipt.md`) — The valid-signature test asserts `branch`/`org_id`/commit fields **from the HTTP response body**, which binds 2.1.2 to echo the parsed `PushEvent` back in the response. At this task's stage that echo is the only observable proof that parsing worked, so it is a reasonable contract-test choice (and the plan flags "assert the observable HTTP contract"). But a production webhook receiver normally returns a minimal `200` and hands the event to a pipeline rather than echoing it. When the real downstream consumer lands, revisit whether the receipt endpoint should still serialize the full event into its response, or whether the test's observability hook should move to the pipeline seam — so the response shape isn't frozen purely by a red test. [dismissed]
- Affects: local-dev tooling (`Makefile` `dev`/`eval`, `scripts/*.py`) — Making `github_webhook_secret` a *required* `str` with no default means any run that instantiates `Settings` now needs the key present. `make run` is safe (nothing instantiates `Settings`), but `scripts/eval.py`/`scripts/summarize_range.py` call `get_settings()`, so `make dev`/`make eval` will raise `ValidationError` if `GITHUB_WEBHOOK_SECRET` is entirely **absent** from `.env.dev`. An empty value (`GITHUB_WEBHOOK_SECRET=`, as in `.env.example`) satisfies `str` and is fine; the hazard is only total absence. Spec mandates the required-no-default shape, so this is by design — just worth confirming `.env.dev` carries the (possibly empty) key so the summarization slice keeps running. [dismissed]
