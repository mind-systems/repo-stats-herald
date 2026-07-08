# 6.2 — Coordination-root seeding

**Phase:** 6 — Project graph & the cross-project surface. Depends on 6.1 (the graph) and Phase 3 (the mirror, to read `CLAUDE.md` from an isolated tree; and 3.6, which this wires into). Derives precise edges from an authoritative coordination root.

## Current state

After 6.1 the graph holds operator-declared edges. A coordination-root repository — one whose `CLAUDE.md` states it is a "coordination layer" and lists its sub-projects and the contracts between them (proto ownership, auth spans) — carries an authoritative membership/contract list, but nothing turns it into graph edges. It is in the knowledge store (retrieval finds it fuzzily), yet as an authoritative list it deserves **precise** edges.

Two gaps in the original design: it read `CLAUDE.md` via `RepoMirror.path(repo)`, an API that no longer exists under Phase 3's bare-store + worktree-per-operation model; and it wired into `on_push` without stating whether that means every branch or just the canonical one — under 3.6's branch-gate, `on_push` only fires for the canonical ref, but this task never said so explicitly, leaving "does a `CLAUDE.md` change on a feature branch re-seed the graph?" unanswered.

## Change

On a canonical-ref push (or backfill) touching a coordination-root repo, parse its `CLAUDE.md` and materialize its declared structure as `seed` edges, atomically.

- `src/graph/coordination.py` — `CoordinationSeeder`:
  - `is_coordination_root(claude_md: str) -> bool` — recognizes the shape: a `CLAUDE.md` declaring a "coordination layer" and listing sub-projects (e.g. a repository-structure table of member directories).
  - `seed(repo: str, org_id: int)` — read the repo's `CLAUDE.md` from an **isolated mirror tree at the canonical ref** (`RepoMirror.tree(repo, org_id, canonical_ref)`, 3.1 — the worktree is held open for the read, not a persistent `path()`); if it is a coordination root, parse the member sub-projects and the stated contracts (proto ownership → `CONTRACT`, auth spans → `AUTH`, plain membership → `DEPENDENCY`) into `Edge`s tagged `source=seed`; `ProjectGraph.remove_seed_edges(repo)` then re-insert, **in one transaction** — so a changed `CLAUDE.md` replaces its seeds atomically, and two concurrent seed calls for the same repo can't interleave into a partial or duplicated set.
- Wire into 3.6's `on_push` (already canonical-ref-gated — a push on any other branch never reaches this call) and into 3.6's `backfill`: after either populates semantic memory for the canonical ref, call `seed(repo, org_id)`.

## Files & types

- new `src/graph/coordination.py` (`CoordinationSeeder`)
- edit `src/knowledge/sync.py` (call `seed` from `backfill` / from the canonical-ref-gated `on_push`)

## Guards

- Only the recognized coordination-root shape is seeded; an ordinary `CLAUDE.md` produces no edges.
- Seed edges are keyed by their source repo and **replaced** on re-seed (`remove_seed_edges` then insert, one transaction) — a removed member drops its edge.
- **Remove-then-insert is transactional** — a crash or a concurrent second seed call for the same repo can't leave the graph with neither the old nor the new seed set (no partial state), and two concurrent seeds of the same repo serialize rather than interleaving into duplicates.
- Operator edges (`source=config`) are never touched by seeding (enforced at 6.1.2's conflict-strategy layer, not re-implemented here).
- **The graph tracks the canonical ref's authoritative structure, like semantic memory — never a feature branch.** Because seeding is wired inside 3.6's `on_push`, which only runs on the canonical ref, a `CLAUDE.md` change on a feature branch never re-seeds the graph.
- Reads the `CLAUDE.md` from an isolated mirror tree — no network fetch here.

## Verification

- A coordination-root `CLAUDE.md` listing members `a/api`, `a/mobile` with a proto-ownership note → `seed` produces the corresponding `CONTRACT`/`DEPENDENCY` edges tagged `source=seed`.
- Editing that `CLAUDE.md` to drop a member and re-seeding removes the dropped member's edge and leaves operator edges intact.
- An ordinary (non-coordination) repo's `CLAUDE.md` → `seed` adds nothing (false-positive check).
- A genuine coordination-root `CLAUDE.md` is correctly recognized and seeded (false-negative check).
- The member/contract parse maps proto ownership → `CONTRACT`, auth spans → `AUTH`, plain membership → `DEPENDENCY` — each kind verified against a fixture with all three.
- A `CLAUDE.md` change on a **feature branch** does not re-seed the graph — only a canonical-ref push or a backfill does.
- Two concurrent `seed` calls for the same repo leave the graph in a consistent end state (the last transaction's edge set), never a partial mix of old and new.
