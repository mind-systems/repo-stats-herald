# 20.2.1 — Concurrency contract for the async mirror (red scenarios)

**Phase:** 20 — Thin the ingestion router. Independent of 20.1. Precedes 20.2.2, which must satisfy the invariants pinned here.

## Current state

Every `RepoMirror` method that shells out to git runs synchronously start to finish, with no internal yield point, so a call from an async context executes atomically with respect to the event loop — nothing else can interleave inside it. Two invariants rest on that accident today: `ensure`'s "clone if the bare path is absent, else fetch" branch, and the lock-guarded reclamation of finished worktrees. The mirror's own governing task spec states it introduces no concurrency surface beyond what the original mirror-isolation contract pinned; that contract covered a torn tree and double token minting under this execution model.

## Change

Define, and pin with red scenarios, the invariants the async conversion must preserve once those yield points exist. Four scenarios, each driving a deterministic interleaving over a controlled git subprocess: two overlapping `ensure` calls for a repo with no bare clone yet never both take the clone branch; the finished-worktree bookkeeping stays consistent when reclamation interleaves with registration under real threads; a worktree prune never removes a worktree that is being created; and an `ensure` overlapping a `tree` for the same repo still never shares a mutable checkout.

## Files & types

- edit `tests/github/test_mirror_isolation.py` (the concurrency home of the split-out mirror suite — add the four concurrency scenarios)

## Guards

- No production code lands and no synchronization mechanism is chosen — a per-repo lock is one plausible answer, but selecting it belongs to the implementing task, which must answer to these scenarios rather than the reverse.
- The scenarios are red against today's synchronous implementation only where the async conversion would make them reachable, and each states which of the two it is.
- A scenario may be red-only by construction. Where the harness can force the interleaving only while the defect is present, the conversion task relaxes that gate rather than inheriting a scenario expected to turn green unchanged; what survives the conversion is the invariant the scenario asserts, not the mechanism that forces it.
- `GitHubAppAuth`'s single-flight token cache is already guarded by a per-org `threading.Lock` written for thread concurrency, so double-minting is out of scope here and is not re-pinned.

## Verification

- Each scenario fails or is inapplicable against the current synchronous mirror for a stated reason, and expresses an invariant the conversion must satisfy.
- No file under `src/` changes.
