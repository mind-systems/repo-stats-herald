# 3.1.2 — Repo mirror (impl)

**Phase:** 3 — Repo mirror & semantic memory. Depends on 3.1.1 (the isolation + single-flight contract and its red tests). Second half of the mirror milestone — turns 3.1.1's tests green.

## Current state

3.1.1 defines the `RepoMirror`/`GitHubAppAuth` surface and pins its isolation + single-flight invariants with red tests. The stubs raise for every call — no clone, no worktree, no token minting exists yet.

## Change

Implement the mirror over a per-repo bare object store, serving each operation its own isolated `git worktree` at a pinned ref — so concurrent same-repo operations never share a mutable tree — and a single-flight-cached App token.

- Extend `src/core/config.py` `Settings` with `github_app_id: int`, `github_app_private_key_path: str`, and `mirror_root: str` (a directory; a persistent volume in prod).
- `src/github/app_auth.py` — `GitHubAppAuth.token(org_id) -> str`: build an App JWT (RS256 from the PEM at `github_app_private_key_path`) → resolve the org's installation → mint an installation access token; **single-flight per org** (concurrent callers near/after expiry await one in-flight mint rather than each minting their own), cached until shortly before expiry. The token doubles as a git credential, passed per-command, never persisted in an `origin` URL.
- `src/github/mirror.py` — `RepoMirror`:
  - `ensure(repo: str, org_id: int) -> None` — a bare `git clone --bare` of `repo` into `{mirror_root}/{repo}.git` if absent (the one shared, immutable-by-convention object store; nothing checks out directly against it), else `git fetch` to bring its refs current.
  - `tree(repo: str, org_id: int, ref: str) -> ContextManager[Path]` — `git worktree add` a fresh isolated working tree at `ref` off the bare store into a scratch directory, yields its path, `git worktree remove` on exit (context-manager cleanup, always runs). Each call gets its own tree; concurrent calls for the same repo at different (or the same) ref never observe each other's checkout.
- Assembled at the composition root; the token from `GitHubAppAuth` is injected as the credential.

## Files & types

- edit `src/core/config.py` (`github_app_id`, `github_app_private_key_path`, `mirror_root`)
- edit `src/github/app_auth.py` (stub → `GitHubAppAuth` implementation)
- edit `src/github/mirror.py` (stub → `RepoMirror` implementation)

## Guards

- **Full clone — no sparse/partial.** The mirror carries no per-project "what matters" policy (that lives in 3.4). A shallow `--depth` is a possible later global tuning knob, never a file-selection choice.
- PEM from the env path only; the token is **never** persisted in the bare store's `origin` URL and never logged.
- Worktrees are always cleaned up on exit (no disk leak) — a crash mid-operation must not orphan a worktree indefinitely (a startup sweep or explicit cleanup handles the rare leak).
- Force-push tolerated by construction — each operation checks out a pinned ref fresh; there is no persistent checked-out tree to diverge.
- Turns 3.1.1's tests green — introduces no new concurrency surface beyond what 3.1.1 already pinned.

## Verification

- 3.1.1's red test suite passes green against this implementation.
- `ensure(repo, org_id)` on a served repo produces a bare object store; a second call fetches, doesn't re-clone.
- `tree(repo, org_id, ref)` yields a working tree pinned at `ref`; two concurrent calls for the same repo at different refs each see only their own ref, and both clean up without disturbing the other.
- Phase 1's `GitCommitCollector` runs against a yielded tree path and returns a populated `CommitContext`.
