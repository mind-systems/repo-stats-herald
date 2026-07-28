# 23.1 — Read git paths in the encoding Python expects

**Phase:** 23 — Clear the way for the coverage pass. The one task in the phase that changes behaviour rather than opening a seam; by shape it belongs to Phase 19's family of boundary representation mismatches, and it lands here instead so the whole coverage prerequisite ships as one unit. Touches the same log invocation as 23.2, so land them in order — this one first, being the smaller change.

## Current state

`GitCommitCollector.collect` runs its `git log` with the numstat and shortstat options but leaves git's path-quoting setting at its default. Git then renders any path byte outside ASCII as a double-quoted, octal-escaped string, so a repository holding a file with a non-Latin name yields a changed-file entry that is an escape sequence rather than the path itself. That entry is what the summariser renders into its prompt, what the linked-change resolver compares against the source strategy's selections, and what the code-derived path of the episodic backfill hands to its blob reads — so in every one of those places the value is plausible, is never equal to a real path, and raises nothing. The sibling method that lists a commit's changed paths already disables the quoting explicitly and carries a comment saying why; only the log invocation behind `collect` was left at the default.

## Change

Disable git's path quoting on the log invocation `collect` issues, matching the sibling method that already does so. The parsing that consumes the output is unchanged — the fix is at the boundary that produces the value, not at the code that reads it.

## Files & types

- edit `src/commits/collector.py` (the git invocation behind `GitCommitCollector.collect`)

## Guards

- Only the log invocation changes; no regex, no field splitting, and no record framing in the parsing helpers is touched.
- The sibling path-listing method is already correct and is not edited.
- An all-ASCII repository produces byte-identical output to today, so no existing behaviour or captured evaluation output shifts.
- Paths that git quotes for reasons other than encoding — an embedded newline or quote character — are out of scope; this task addresses the encoding case only and must not add unquoting logic to compensate for the rest.

## Verification

- A commit touching a file with a non-Latin name yields that name literally in the collected context, not an escape sequence.
- The same commit's path is equal to what the sibling path-listing method reports for it.
- A commit touching only ASCII paths yields exactly what it yields today.
