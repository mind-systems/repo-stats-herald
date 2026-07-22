# 3.1.1 — Mirror isolation & auth contract (red scenarios)

**Phase:** 3 — Repo mirror & semantic memory. First task. The generic "read repo content" engine's safety contract — isolation and auth, pinned with tests, ahead of the implementation (3.1.2).

## Current state

Herald keeps no copy of any repo. The webhook payload (task 2.1's `PushEvent`) carries paths and commit metadata but **not content**. `Settings` reads `github_webhook_secret` but not the App identity (`GITHUB_APP_ID`, `GITHUB_APP_PRIVATE_KEY_PATH` are in `.env.dev`/`.env.example`, unread). Nothing pins the concurrency contract a shared mirror needs: two pushes to the same repo racing on one mutable working tree would let one operation silently index a tree another just reset out from under it (a torn tree — plausible-looking, no crash); concurrent requests near a cached installation token's expiry could double-mint.

## Change

Define the `RepoMirror`/`GitHubAppAuth` surface and pin its isolation + single-flight invariants with red tests, before any git/HTTP logic exists.

- `src/github/app_auth.py` — a STUBBED `GitHubAppAuth` (`token(org_id) -> str`, raises `NotImplementedError`).
- `src/github/mirror.py` — a STUBBED `RepoMirror` (`ensure(repo, org_id)`, `tree(repo, org_id, ref) -> ContextManager[Path]` — an isolated working tree at a pinned ref, checked out via `git worktree add`/`remove` around one per-repo bare object store, torn down on exit — raises for now).
- Write red tests pinning:
  - **isolation** — two concurrent `tree()` calls for the same repo at different refs each see only their own ref's content; neither observes the other's checkout, before or after either completes;
  - **single-flight token** — N concurrent `token(org_id)` calls near/after expiry result in exactly one mint, all callers seeing the same fresh token;
  - **cleanup safety** — one operation's worktree teardown does not disturb a concurrent operation's still-open worktree.

## Files & types

- new `src/github/__init__.py`, `src/github/app_auth.py` (stub `GitHubAppAuth`), `src/github/mirror.py` (stub `RepoMirror`)
- new test file(s) covering the three scenarios above, run against the stubs (red)

## Guards

- Tests-first: no git subprocess calls, no HTTP calls — pure surface + red tests; 3.1.2 turns them green.
- Isolation is by **construction** (worktree-per-operation off one bare store), not by locking — the torn-tree race dissolves because no two operations ever share a mutable tree, not because they take turns on one.
- Single-flight is asserted for the token cache specifically — the shared, stateful surface a naive per-request mint would race on.

## Verification

- The concurrency test suite added here is red against the stubs (fails only because there's no logic yet — no import errors, no fixture errors).
- Compiles and boots; the stub surface is reachable and raises for any call.
- Each of the three pinned scenarios (isolation, single-flight token, safe cleanup) has a corresponding red test.
- The single-flight test **discriminates**: it reliably *fails* a naive per-request mint (one that mints without holding the cache across the mint), not merely passes a correct single-flight implementation — so a later regression to plain per-request caching cannot slip through green. The test forces the concurrent callers to overlap while a mint is in flight; a mint that is instantaneous and unsynchronised does not pin the invariant.
