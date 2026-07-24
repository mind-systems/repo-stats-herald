# 6.2 — Coordination-root seeding

**Phase:** 6 — Project graph & the cross-project surface. Depends on 6.1 (the graph) and Phase 3 (the mirror, to read `CLAUDE.md` from an isolated tree; and 3.6, which this wires into). Derives precise edges from an authoritative coordination root.

## Current state

After 6.1 the graph holds operator-declared edges. A coordination-root repository — one whose `CLAUDE.md` states it is a "coordination layer" and lists its sub-projects and the contracts between them (proto ownership, auth spans) — carries an authoritative membership/contract list, but nothing turns it into graph edges. It is in the knowledge store (retrieval finds it fuzzily), yet as an authoritative list it deserves **precise** edges.

Two gaps in the original design: it read `CLAUDE.md` via `RepoMirror.path(repo)`, an API that no longer exists under Phase 3's bare-store + worktree-per-operation model; and it wired into `on_push` without stating whether that means every branch or just the canonical one — under 3.6's branch-gate, `on_push` only fires for the canonical ref, but this task never said so explicitly, leaving "does a `CLAUDE.md` change on a feature branch re-seed the graph?" unanswered.

## Change

On a canonical-ref push (or backfill) touching a coordination-root repo, parse its `CLAUDE.md` and materialize its declared structure as `seed` edges, atomically.

- `src/graph/coordination.py` — `CoordinationSeeder`:
  - `is_coordination_root(claude_md: str) -> bool` — recognizes a coordination root by the marker the [coordination-root format](../../docs/behavior/coordination-root-format.md) defines (its `## Coordination` section). An ordinary `CLAUDE.md` without that section is not a coordination root.
  - `seed(repo: str, org_id: int)` — read the repo's `CLAUDE.md` from an **isolated mirror tree at the canonical ref** (`RepoMirror.tree(repo, org_id, canonical_ref)`, 3.1 — the worktree is held open for the read, not a persistent `path()`). Parse **only** the member table of the [coordination-root format](../../docs/behavior/coordination-root-format.md) — every other table in the file is ignored — into `Edge`s `repo → member` tagged `source=seed`, using the member's **bare `push.repo` identity** on both endpoints (never `org/repo`), with the kind taken from the format (contract → `CONTRACT`, auth → `AUTH`, else `DEPENDENCY`). Then atomically **replace** the repo's `source=seed` edge set with the parsed edges (remove the prior seed rows and insert the current ones in one transaction). If the file is missing or is not a coordination root, replace with the **empty** set — so a repo that stops being a coordination root drops its stale seed edges rather than leaking them. A changed `CLAUDE.md` replaces its seeds atomically, and two concurrent seed calls for the same repo can't interleave into a partial or duplicated set.
- Wire into 3.6's `on_push` (already canonical-ref-gated — a push on any other branch never reaches this call) and into 3.6's `backfill`: after either populates semantic memory for the canonical ref, call `seed(repo, org_id)`.

## Files & types

- new `src/graph/coordination.py` (`CoordinationSeeder`)
- edit `src/knowledge/sync.py` (call `seed` from `backfill` / from the canonical-ref-gated `on_push`)

## Guards

- Only the `## Coordination` member table of the [coordination-root format](../../docs/behavior/coordination-root-format.md) is parsed; any other table in the `CLAUDE.md` (Commands, docs index, …) is ignored and never produces an edge. An ordinary `CLAUDE.md` with no `## Coordination` section produces no edges.
- Seed edges use the **bare `push.repo` identity** on both endpoints (the same key a push carries), never `org/repo`. The whole seed set for a repo is **replaced** on re-seed — a removed member drops its edge, and a repo that stops being a coordination root (marker or file gone) drops all its seed edges.
- **Remove-then-insert is transactional** — a crash or a concurrent second seed call for the same repo can't leave the graph with neither the old nor the new seed set (no partial state), and two concurrent seeds of the same repo serialize rather than interleaving into duplicates.
- Operator edges (`source=config`) are never touched by seeding (enforced at 6.1.2's conflict-strategy layer, not re-implemented here).
- **The graph tracks the canonical ref's authoritative structure, like semantic memory — never a feature branch.** Because seeding is wired inside 3.6's `on_push`, which only runs on the canonical ref, a `CLAUDE.md` change on a feature branch never re-seeds the graph.
- Reads the `CLAUDE.md` from an isolated mirror tree — no network fetch here.

## Verification

- A coordination-root `CLAUDE.md` listing members `api`, `mobile` (bare names) with a contract note → `seed` produces the corresponding `CONTRACT`/`DEPENDENCY` edges tagged `source=seed`, with both endpoints in bare form.
- Editing that `CLAUDE.md` to drop a member and re-seeding removes the dropped member's edge and leaves operator edges intact.
- A coordination-root `CLAUDE.md` that also carries an unrelated table (e.g. a Commands table) seeds edges **only** for its `## Coordination` members — the other table's rows produce no edges.
- A repo that was a coordination root and then drops the `## Coordination` section (or whose `CLAUDE.md` is deleted) has all its seed edges removed on the next canonical push, while operator edges survive.
- An ordinary (non-coordination) repo's `CLAUDE.md` → `seed` adds nothing (false-positive check).
- A genuine coordination-root `CLAUDE.md` is correctly recognized and seeded (false-negative check).
- The member parse maps the format's kinds — contract → `CONTRACT`, auth → `AUTH`, plain membership → `DEPENDENCY` — each verified against a fixture with all three.
- A `CLAUDE.md` change on a **feature branch** does not re-seed the graph — only a canonical-ref push or a backfill does.
- Two concurrent `seed` calls for the same repo leave the graph in a consistent end state (the last transaction's edge set), never a partial mix of old and new.
