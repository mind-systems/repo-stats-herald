# 23.3 — Let a caller supply the mirror's process runner

**Phase:** 23 — Clear the way for the coverage pass. Independent of 23.1, 23.2 and 23.4. Touches the same shared git-invocation helper that 20.2.2 moves onto a thread, so the two must be sequenced deliberately rather than developed in parallel.

## Current state

`RepoMirror` already receives everything a caller needs to steer it: its root directory, its authentication, and the callable that resolves a repository to a clone source all arrive through the constructor, and the canonical-ref resolution helper takes the mirror as an argument. One thing does not. The process invocation is written directly into the shared git helper, and again into the default-branch read, with no parameter offering an alternative.

That matters for exactly one part of the mirror's behaviour: the credentialed clone and fetch path. When the clone source carries an http scheme, the mirror mints an installation token and passes it to git through the process environment rather than through the argument list or the persisted remote — deliberately, so the token never lands in a stored configuration file and never appears in a process listing or in the text of a failure. But that means the guarantee produces no return value and leaves no artefact: the only way to confirm the token travels in the environment, stays out of the argument list, and is absent from the raised failure is to observe the invocation itself. The filesystem clone source the existing fixtures use never takes that branch at all, so a real run cannot exercise it, and the only remaining route is to replace the process call on the module.

## Change

Add an optional constructor parameter for the callable that runs a process, defaulting to what the module uses today, and route both invocation sites through it — the shared git helper and the default-branch read — so there is a single execution seam rather than two. A caller can then pass a recording callable and observe the credentialed path directly.

## Files & types

- edit `src/github/mirror.py` (`RepoMirror.__init__` gains the runner parameter; the shared git-invocation helper and `RepoMirror.default_branch` both route through it)

## Guards

- The parameter is keyword-with-default, so every existing construction — the application composition root, each script entrypoint, and the existing test fixture — is unchanged and keeps using the module's own process call.
- This is a parameter addition only. Worktree-per-operation isolation, credential handling, and the deferred worktree-reclamation timing are all unchanged; nothing about what the mirror runs or in what order changes, only who is asked to run it.
- Both invocation sites route through the one seam. Leaving the default-branch read on its own direct call would keep the mirror's execution split in two and defeat the point.
- 20.2.2 rewrites the same helper to move its work onto a thread. Whichever lands first, the other adapts to it; the runner parameter must survive the async conversion as the same single seam rather than being duplicated per call site.

## Verification

- Constructing the mirror with a recording runner and driving a credentialed clone shows the token present in the process environment, absent from the argument list, and absent from the text and attributes of the failure raised when the command fails.
- Constructing the mirror without the parameter behaves exactly as today against a real repository — clone, fetch, worktree checkout, default-branch read, and the startup sweep all unchanged.
- The default-branch read goes through the same seam as the rest.
