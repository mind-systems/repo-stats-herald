# Code Review: 3.1.1 — Mirror isolation & auth contract (red scenarios)

**Scope reviewed:** new `src/github/{__init__,app_auth,mirror}.py`, new `tests/github/{__init__,conftest,test_app_auth_single_flight,test_mirror_isolation}.py`, plus the doc changes to `ROADMAP.md` and spec `41`. Governing spec `41` and forward-ref `04` consulted.

## What this task is
Signatures-only stub surface (`GitHubAppAuth`, `RepoMirror`) plus red concurrency tests pinning three invariants (isolation, single-flight token, cleanup safety) before any git/HTTP logic exists. The bar is not "tests pass" but "tests fail **for the right reason** — logic absent, never an import/fixture/collection error — and green unchanged in 3.1.2."

## Verification performed
- **Ran `pytest tests/github`:** all 3 tests fail red for the right reason — single-flight on `assert mint_count == 1` (`0 == 1`, because `token()` raises before reaching `_mint_token`); both mirror tests on `ensure()` raising `NotImplementedError`. The `local_upstream` fixture builds a real two-branch git repo (paths/refs materialize in the failure output) — no fixture error.
- **Ran full `pytest`:** 3 failed (the new red tests), 5 passed (pre-existing ingestion suite) — no regression. The one warning is a pre-existing FastAPI/starlette deprecation, unrelated.
- **Import/boot:** `src.main`, `src.github.app_auth`, `src.github.mirror` all import cleanly.

## Correctness assessment

**Stubs.** Signatures match the plan and spec: `GitHubAppAuth(app_id: int, private_key: str)` storing PEM content only (no read/validate → construction can't raise); `token`/`_mint_token` both raise. `RepoMirror(mirror_root, auth, clone_source: Callable[[str, int], str])` stores only; `ensure`/`tree` raise; `tree` typed `AbstractContextManager[Path]`. No `subprocess`/`httpx`/`git` in production code — the "no git/HTTP" guard is honored. No secret is logged.

**Single-flight discrimination is genuine (spec `41` line 36).** The `threading.Barrier(N_CALLERS)` in the worker (not inside the mint — which would deadlock a correct single-flight) forces all 8 callers to hit `token()` simultaneously, and the 0.05s sleep inside `counting_mint` holds the in-flight window open long enough that a naive per-request mint reliably has all 8 enter → `mint_count == 8` (fails), while a correct single-flight mints once → `mint_count == 1`. The window is test-controlled, so a naive impl cannot dodge it; with `max_workers == N_CALLERS` the barrier party count matches the running threads (no hang). Deterministic, not timing-flaky.

**`counting_mint` arity is correct.** `monkeypatch.setattr(auth, "_mint_token", counting_mint)` installs an unbound instance attribute, so 3.1.2's `self._mint_token(org_id)` calls it without `self` — the helper is `def counting_mint(org_id)`, matching. The counter is `threading.Lock`-guarded.

**Green-unchanged seams all present.** `clone_source` lambda points the mirror at `local_upstream` for offline cloning; tests call `mirror.ensure(...)` once before any `tree()` (matching spec `04`'s clone-once / worktree-per-op separation, so `tree()` need not auto-`ensure`); the retained `_mint_token` gives 3.1.2 a stable delegate. The isolation test reads `marker.txt` (content-a/content-b) off distinct worktree paths — the assertions 3.1.2's worktree-per-operation impl must satisfy. Fixture determinism is pinned: explicit committer identity (`-c user.name/user.email`), `git init -b <ref>` + `checkout -b <ref>`, and tests drive off the yielded ref names, never a hardcoded `main`/`master`.

**Doc changes** are limited to the discrimination clause in spec `41` and the mirrored phrase in the `3.1.1` roadmap line — consistent with the code, no stray edits.

## Findings
None. The stubs are minimal and correct, the tests are red for the right reason (verified by running), the single-flight test discriminates as the spec now requires, and every seam the "green unchanged in 3.1.2" promise depends on is in place.

REVIEW_PASS
