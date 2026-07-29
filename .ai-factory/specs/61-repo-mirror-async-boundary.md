# 20.2.2 — Give `RepoMirror` an async boundary

**Phase:** 20 — Thin the ingestion router. Independent of 20.1 — touches the mirror's call shape, not orchestration placement. Depends on the preceding contract task, which owns the concurrency invariants and their red scenarios.

## Current state

Every `RepoMirror` method that shells out to git — ensuring a repo's mirror is fresh, checking out a worktree, reading the default branch, and the startup worktree sweep — bottoms out in one internal helper's blocking process call. Every caller of `RepoMirror` already runs inside an event loop: the webhook's background tasks, the application's startup lifespan (which runs the worktree sweep once before serving), and each of the standalone script entrypoints, all of which already define an async entrypoint and already drive it with `asyncio.run`. A `git fetch` against an existing mirror, or a first `clone` of a new one, is therefore a blocking call sitting on the event loop, stalling every concurrent request for as long as it runs.

## Change

Move the blocking git work onto a thread from inside `RepoMirror` itself, so every method that shells out becomes awaitable, and update every caller — the webhook-triggered background paths, the knowledge sync, the episodic writer, the coordination seeder, the startup sweep, and each script entrypoint — to await them. Whatever synchronization the preceding task's pinned invariants require is this task's decision to make against them.

## Files & types

- edit `src/github/mirror.py` (`RepoMirror.ensure`, `.tree`, `.default_branch`, `.sweep_worktrees`, and the internal git-invocation helper they share)
- edit `src/ingestion/router.py` (the release fan-out's mirror call)
- edit `src/knowledge/sync.py` (the mirror calls in the knowledge-sync path)
- edit `src/episodic/writer.py` (the mirror calls in the episodic-write path)
- edit `src/graph/coordination.py` (the mirror calls in the coordination-seeding path)
- edit `src/main.py` (the startup sweep call in `lifespan`)
- edit each `scripts/*.py` entrypoint that calls into the mirror

## Guards

- The thread-offload mechanism lives inside `RepoMirror` once and is never duplicated at a call site.
- No `asyncio.run` is added anywhere — every caller already has one at its own entrypoint.
- Worktree-per-operation isolation must still hold once the git calls are awaitable — concurrent operations on the same repo must never share a mutable checkout. This is not assumed to carry over unchanged; the preceding task's red scenarios are what demonstrate it holds under the interleavings the conversion introduces.
- Credential handling through the git process environment is unchanged.
- The deferred worktree-reclamation timing — a finished worktree reclaimed on the repo's next mirror-refresh rather than immediately — is unchanged.
- The conversion genuinely widens `RepoMirror`'s concurrency surface: methods that run atomically with respect to the event loop today gain yield points once their git work is offloaded, so interleavings unreachable today become reachable. This task satisfies the invariants the preceding contract task pins — it does not assume equivalence with the synchronous mirror.
- At least one of the preceding contract task's scenarios is red-only by construction: its forcing harness can hold both threads on the same branch only while that branch is unserialized. Once this conversion serializes it, the second thread never reaches the gate, so the gate is relaxed here as part of the conversion rather than inherited untouched — inherited untouched it hangs rather than passes. The invariant that survives is the one the scenario asserts, not the harness that forced it.

## Verification

- A long-running git fetch no longer blocks a concurrent request from being handled while it runs.
- Existing mirror behavior — isolation, reclamation timing, credential passing — is unchanged under test.
- Every caller, including each script entrypoint, still runs end to end with no behavior change.
