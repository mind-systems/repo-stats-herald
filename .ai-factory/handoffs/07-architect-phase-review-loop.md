# Architect — resuming the phase-by-phase lens review

## 1. Frame

You are the **architect** in a paired architect↔editor loop, planning this project one
roadmap phase at a time with a spec-before-code lens — the originating session's context is
gone, so trust these files, not memory.

## 2. Read-first map

Scoped to the next step (the **Phase 9** lens pass), not the whole project.

### Must-read now (minimal rehydration set)
- `.ai-factory/handoffs/architect-buffer.md` — **lead here.** Your private deferred items **plus
  a survive-compact anchor**: the delivery-cadence revision that lands in phases 9–11, the
  eval-harness-generalization item, the settled model, and your lens principle. This is the one
  file that is yours to edit.
- `.ai-factory/ROADMAP.md` — the two-tier roadmap. **Read the current Phase 9 fresh**: its
  `2.3 → 9.1` relocation already happened (the delivery-plan resolver moved out of Phase 2), but
  Phase 9 has **not** had the lens pass yet — don't assume its shape from memory.
- `docs/spec/delivery.md` — the Phase 9–12 behavioral target; the cadence revision rewrites its
  "Telegram fires on every push."
- Phase 9 specs: `.ai-factory/specs/03-delivery-plan-resolver.md` (=9.1),
  `15-telegram-client.md` (=9.2), `16-telegram-delivery.md` (=9.3).
- `.ai-factory/handoffs/06-editor-phase-decomposition-loop.md` — what the editor knows, so your
  work-orders land in its frame.

### Read on demand
- `docs/architecture.md` — the two-memory / reasoner model (the domain spine below is the digest).
- `CLAUDE.md` — project guide (status, stack, commands).
- `.ai-factory/handoffs/02–05` — earlier planning handoffs (merge, re-sequence, review).

## 3. Current state

**Done:** Phase 1 (summarizer spike) is built; **phases 2–8 lens-reviewed and committed** — tasks
decomposed, split where the lens called for it, spec gaps closed.

**In-flight:** nothing mid-task — clean phase boundary.

**Uncommitted working-tree state:** this handoff and the updated `architect-buffer.md` (commit
only on explicit permission).

## 4. Next step

Lens-review **Phase 9 (Delivery & routing)** — but it is **entangled with the buffered
delivery-cadence revision**: per-push becomes memory-only (no per-push Telegram), reports become
a **daily + weekly digest** cadence plus event reports on **RC (staging)** and **release
(master)**. That revision reshapes phases 9–11, rewrites `docs/spec/delivery.md`, and fixes the
now-stale per-push references in specs 25 and 30. So the Phase 9 pass folds the cadence rework
in, not just skeleton/TDD/concurrency splits. Then phases 10, 11, 12, backlog. Draft the Phase 9
work-order for the editor; the editor applies and reports; you verify by fact.

## 5. Working discipline

Draft **one self-contained fenced work-order per change** and hand it to the editor; **never edit
the shared artifacts yourself**. When the editor reports, **verify by fact** — run your own
greps/reads against the files and check its judgment calls on the file, not on the note. On a
review, form **your own verdict first**, then **reconcile** with the editor's: concede where its
catch is sharper (say why), hold where the principle says so (say why), draft the work-order only
for what survives. The user rules the marginal forks and owns the commits — **commit only on
explicit permission**, via the roadmap-update commit.

## 6. Domain model spine (don't re-litigate)

- **Two memories:** *semantic* ("what the project is now", built from ONE canonical ref =
  `staging`, config; **never a store per branch**) and *episodic* (append-only, one entry per
  push, all branches, "how it changed"). **Branch-gate:** semantic syncs only on the canonical
  ref; a feature-branch push updates episodic + is narrated, never semantic.
- **Reasoner** over both memories — a concrete class; the swap seam is the injected `LLMClient`;
  entitlement tiering is Phase 14 and adds zero reasoner-side code.
- **Mirror** = a per-repo bare object store + a `git worktree` per operation at a pinned ref
  (isolation by construction, not locking) + a single-flight token cache; callers get an isolated
  tree at a ref.
- **Append-only stores + worktree isolation** make concurrent writes/reads safe by construction.
- **Delivery/broadcast is a projection** over the core, not the point of it; its cadence is under
  the revision in the buffer.

## 7. Lens principle

- A **seam** (an ABC, 2+ implementations, or a non-obvious shared contract) → split into a
  contract+red-tests milestone (`N.M.1`) → an impl milestone (`N.M.2`, which greens it).
- A **concrete** function on an existing class → **no split**; fold a mandatory test + a guard
  straight into its own spec.
- An **LLM-output** surface (model-generated prose) → the **eval harness** verifies it against a
  user-authored reference; only the deterministic mechanics around the model get pinned tests.
- A **concurrency** contract-task only for a heavy task touching ≥2 hazard classes (append-only /
  worktree usually dissolve the hazard first).
- Be **adversarial** — name the specific plantable failure, not a vague caution — and **hunt
  propagation gaps**: a decision from an earlier phase that never reached a file (e.g. the mirror
  API `path()` → `tree()`, the branch-gate). **Most reviewed tasks pass through; splitting is the
  exception.**

## 8. Hard rules / traps

- **Family references** (`N.M` after a split into `N.M.1…k`) stay valid — **never sweep them**;
  only the split lines and the specs a work-order names change.
- **Collision-safe remaps** (renumbers, overlapping-number remaps): map from the **original text
  in one pass**, never a cascading find-and-replace.
- The **buffer is architect-only** — the editor never reads, touches, or is told of it.
- **Commit only on explicit permission.** **Planning only** — the orchestrator implements the
  specs in a separate run; we never write application code here.
