# 23.2 — Make the commit-log parse reachable without a repository

**Phase:** 23 — Clear the way for the coverage pass. Independent of 23.3 and 23.4, which open the same kind of seam in the mirror and the model boundary. Touches the same log invocation as 23.1, which lands first. Deliberately does not touch the commit-range comparison whose failure signalling is owned by 18.2.1 and 18.2.2.

## Current state

`GitCommitCollector.collect` accepts a repository path and a revision range, shells out to git through a private helper, and hands the resulting text to the parsing helpers that split it into records, separate the fields, and read the per-file statistics into a commit context. That context is the sole input to the summariser's prompt, to the linked-change resolver, and to the episodic backfill, so every parse defect becomes wrong prose rather than an error — and yet the parse itself is reachable only through a real repository, because the raw text is produced inside the call and no parameter offers it.

For most shapes that is merely inconvenient; the existing repository fixtures make an ordinary commit cheap to build. For the shapes the parse is actually most fragile against it is worse. A record-separator byte inside a commit subject is legal in git and is precisely what breaks the record framing, but reaching it means constructing that commit and hoping the framing behaves as expected rather than asserting on the framing directly. Statistics shapes that need hundreds of files, or a rename rendered in git's brace-compressed form, cost a repository build each. The only alternative today is to intercept the process call, which means asserting on the parse through a patch of a module global rather than by passing a value.

## Change

Expose the raw log text as a value the collector's own API accepts: a public parse entry point taking that text together with the repository and branch labels the context carries, returning the same commit context `collect` returns today. `collect` keeps its signature and its behaviour, shells out as it does now, and delegates to the new entry point. Nothing about how records are framed, fields separated, or statistics read changes — the logic moves behind a name that can be called with a value.

## Files & types

- edit `src/commits/collector.py` (`GitCommitCollector` — add the public parse entry point; `collect` delegates to it, its private git-invocation helper keeps shelling out)

## Guards

- `collect`'s signature, return type, and observable behaviour are unchanged; this is additive.
- No parsing rule is altered in passing — the record framing, the field separation, the numstat and shortstat reading, and the subject-and-body joining all keep their current behaviour exactly, including their current defects. Anything to be fixed there is a separate task with its own reason to revert.
- The commit-range comparison and its empty-versus-failed distinction are untouched; that contract belongs to 18.2.1 and 18.2.2 and this task must not pre-empt it.
- The new entry point is a parse over text, not a second way to reach git — it must not acquire a repository path, shell out, or read the filesystem.

## Verification

- The parse entry point turns a captured log text into the same commit context that running `collect` against the repository that produced it returns.
- A record-separator byte inside a subject, a brace-compressed rename, and a several-hundred-file statistics block can each be exercised by passing text, with no repository built and no module patched.
- Every existing caller of `collect` is unchanged and behaves as before.
