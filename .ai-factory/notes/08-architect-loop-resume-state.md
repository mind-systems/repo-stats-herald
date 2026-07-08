# Architect loop — resume state (archived buffer)

> **Archived snapshot** of the architect's private working buffer at the clean stop after the active roadmap (phases 2–12) was lens-reviewed. Its deferred queue is empty; what remains is the survive-compact resume anchor (operating discipline, lens principle, settled model, hard rules) kept for a future resume. Ground truth is the ROADMAP/specs/docs; this is a fast orientation, not authoritative. Originally `.ai-factory/handoffs/architect-buffer.md` — the architect's own clipboard, editor-invisible.

---

## Deferred items

_(none — all deferred items resolved)_

---

## Survive-compact anchor (architect resume state)

**Where we are:** planning this project as a paired architect↔editor loop, phase by phase, spec-before-code lens. Phase 1 built; **the whole active roadmap (phases 2–12) is lens-reviewed and committed** (latest `Roadmap update` = `7c30f39`). Everything above `---STOP---` is orchestrator-ready; specs↔ROADMAP↔docs are consistent. Phase 11 unified the release note onto the report engine (`Report([SummarySection], SinceDeployWindow)` via `report_notes`) with the full `digest→report` rename; Phase 12 closed the "unreachable app never blocks other channels" invariant (config+entry isolation) and routed the changelog target through the resolver (`DeliveryPlan.changelog_base_url`). Working tree clean. **Editor is now a real subagent** (reach it via SendMessage). **Deferred queue empty** — eval-harness generalization became a Phase-1 task (`specs/52-eval-harness-case-types.md`) and the README was rewritten to the reasoner/reports model. **Next: nothing pending**; the backlog (13 deploy, 14 multi-tenant/tiering, 15 conversation, already decomposed) sits below `---STOP---`, promote only if prioritized.

**How I work (architect side):** draft **one self-contained fenced work-order per change** for the editor; **verify the editor's report by fact** (grep/read the files, check its judgment calls on the file, not the note); run my own review then **reconcile** with the editor's (concede sharper catches with the reason, hold on principle with the reason, task only for survivors); the user rules marginal forks and owns commits (**commit only on explicit permission**, via the roadmap-update commit). **Override in force:** the user made docs/ТЗ *"наша ответственность"* — the architect edits `docs/**` directly; **specs + ROADMAP still go through the editor**.

**Lens principle (how I split):** a **seam** (ABC / 2+ impls / non-obvious shared contract) → split into a contract+red-tests milestone (`N.M.1`) → impl (`N.M.2`). A **concrete** function on an existing class → no split; fold a mandatory test + guard into its own spec. **LLM-output** surface → the **eval harness** verifies (not unit tests); only the deterministic mechanics around the model get pinned tests. **Concurrency** contract only for heavy + ≥2 hazards. Adversarial — name the plantable failure; hunt **propagation gaps** (a decision from an earlier phase that never reached a file). **Most reviewed tasks pass through — splitting is the exception.**

**Settled model — do not re-litigate** (pointers: `docs/architecture.md`, `docs/spec/*`):
- Two memories: **semantic** ("what is now", ONE canonical ref = `staging`, config; **never per-branch**) + **episodic** (append-only, every push, all branches, "how it changed"). branch-gate: semantic syncs only on the canonical ref.
- **Reasoner** over both — concrete class, swap seam = injected `LLMClient`; tiering is Phase 14 (zero reasoner-side code).
- **Mirror** = per-repo bare store + `git worktree`-per-operation (isolation by construction) + single-flight token; callers get an isolated tree at a ref.
- **Append-only stores + worktree isolation** make concurrent writes/reads safe by construction — no locks.
- **Cadence settled:** a served push is **memory-only** (never reported per push); delivery fires as **reports** (daily/weekly, cron) and **release milestones** (staging/default push, versioned). Reports & release notes share ONE engine: `Report` = ordered `ReportSection`s over a `ReportWindow` (ABC: `TimeWindow` / `SinceDeployWindow`), localized via `report_notes`; sections `SummarySection` / `PerBranchSection` / `RemainingSection`; composition is config (`Settings.report_schedules`). `DeliveryService.deliver(plan, note)` is the shared sink; the resolver's `branch_role` gates only the milestone path (reports are branch-agnostic).

**Hard rules:** family references (`N.M` after a split) stay valid — **never sweep**. Collision-safe remaps: **map from original, one pass**. This buffer is architect-only — the editor never sees it. Commit only on explicit permission. Planning only — the orchestrator implements, not us.
