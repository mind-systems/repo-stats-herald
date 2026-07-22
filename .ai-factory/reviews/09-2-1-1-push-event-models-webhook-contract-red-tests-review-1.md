# Code Review: 2.1.1 — Push-event models + webhook contract (red tests)

**Scope:** `git diff HEAD` / `git status` — source: `src/ingestion/models.py`, `src/ingestion/router.py`, `src/ingestion/__init__.py`, `src/main.py`, `src/core/config.py`; harness: `pyproject.toml`, `Makefile`, `tests/conftest.py`, `tests/ingestion/__init__.py`, `tests/ingestion/test_webhook_contract.py`. (Plan/plan-review/`.json` artifacts are not code and were not reviewed for behavior.)

**Verdict:** Faithful to the spec and the plan. All five tests run **red for the right reason** — verified by execution, not inspection. One low-severity, non-blocking structural nit in the test-package layout.

## What was verified by running it

- **Tests are red, and red for the right reason.** `uv run pytest` → `5 failed, 1 warning`. Every failure is an `assert <expected> == 501` on the response status (stub returns `501`); there are **no** collection errors, import errors, or fixture errors. This is exactly the task's central guard ("fail because the stub lacks logic, never because of an import/fixture error").
- **`src` is importable from tests.** `pythonpath = ["."]` in `[tool.pytest.ini_options]` puts the project root on `sys.path`, so `from src.main import app` in `conftest.py` resolves. This was the plan-review-1 critical fix and it is correctly applied.
- **Boot-safety of the required `github_webhook_secret`.** `env -u GITHUB_WEBHOOK_SECRET python -c "from src.main import app"` imports cleanly and serves `/health` — nothing instantiates `Settings` at import/boot on the web path, so the required-no-default field introduces no regression. (`get_settings()` is only reached when 2.1.2 adds verification; the fixture supplies the value by then.)
- **Route is registered and reachable.** The tests POST to `/webhooks/github` and receive `501` (not `404`), confirming `app.include_router` wired the stub. The `_IncludedRouter` entry seen when iterating `app.routes` is FastAPI's lazy-inclusion wrapper (route resolves at request time), not a mis-registration.

## Correctness / spec conformance

- **Models** (`models.py`) match the spec field-for-field and copy the established `@dataclass(frozen=True, slots=True)` + `tuple[...]` pattern from `src/commits/models.py`. `org_id: int` vs `org_login: str` split preserved.
- **Stub** returns an explicit `501` (does not raise), keeping the red run clean — the spec-allowed option the plan selected.
- **Contract coverage** is complete: valid signature → 200 + populated event (with `ref`→`branch` strip proven via both `main` and `feature/x`, and `org_id` pinned as the numeric id, distinct from `org_login`); tampered signature → 401; **absent** signature → 401 (the named hazard, asserted in its own test); non-`push` (validly signed) → 204, which also pins verify-before-branch ordering.
- **Signing helper** uses `hmac.new(secret, body, sha256)` with the `sha256=` prefix — the exact `X-Hub-Signature-256` shape 2.1.2 will verify, signed with the same secret the fixture injects.

## Findings

### Low — inconsistent test-package layout; conftest is imported twice and prepend-mode collisions are latent

`tests/ingestion/__init__.py` exists but `tests/__init__.py` does **not**, while `tests/ingestion/test_webhook_contract.py:9` does `from tests.conftest import TEST_ORG_ID, TEST_ORG_LOGIN`.

It works today (namespace-package resolution + `pythonpath=["."]`), but it has two consequences:
- **`conftest.py` is imported twice** — once by pytest as top-level module `conftest` (because `tests/` is not a package, so prepend mode drops `tests/` on the path and imports basename-only), and again as `tests.conftest` for the constant import. Harmless now (the shared names are plain int/str constants; fixtures are resolved through pytest's own conftest mechanism), but it is a smell.
- **Latent prepend-mode collision.** With `tests/ingestion/` as the topmost `__init__`-bearing package, the test module imports as `ingestion.test_webhook_contract`. When a second test directory later also contains an `ingestion` subpackage, pytest raises the classic "import file mismatch" error. This is the first test in the repo, so the layout it sets is the one the suite inherits.

**Suggested fix (minimal, consistent):** add an empty `tests/__init__.py`. That makes `tests` a real package, so modules import as `tests.ingestion.test_webhook_contract` (no basename collisions), and `from tests.conftest import …` becomes a single ordinary import instead of a second load. Non-blocking — the tests pass/fail correctly as-is.

## Notes (not findings)

- The valid-signature test reads `branch`/`org_id`/commit fields from the **HTTP response body**, binding 2.1.2 to serialize the parsed `PushEvent` back into the `200` response. Already captured as a deferred observation in the plan; flagging here only so it is not mistaken for an oversight. At this stage the echo is the sole observable proof of parsing.
- The `StarletteDeprecationWarning` (httpx/TestClient) is pre-existing environment noise, unrelated to this change, and does not affect results (warnings are not errored).
