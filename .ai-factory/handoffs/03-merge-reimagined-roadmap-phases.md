# Handoff — merge-reimagined-roadmap-phases

## 1. Frame
Herald (`repo-stats-herald`, branch `dev`) has been reframed this session from a push-narrator into a **conversational service over each project's understanding and evolution**; the next job is to **merge the reimagined phase outline (Phase 13–26, below the final `---STOP---`) into the decomposed phases at the top (Phase 1–12)** so the top plan reflects the new model — the originating session's context isn't available here; trust these files, not memory.

## 2. Read-first map

### Must-read now (minimal rehydration set)
- `.ai-factory/ROADMAP.md` — the file to edit. Top: Phase 1 (`[x]` done, specs in `notes/`) + Phase 2–10 decomposed into 23 tasks **above the first `---STOP---`** + Phase 11–12 backlog prose. Bottom, **below the final `---STOP---`**: the reimagined `## Herald reimagined` direction, Phase 13–26. The merge folds bottom into top.
- `docs/architecture.md` → section **`## The two engines over the event stream`** — the formalized model every merged phase must reflect: event stream → derivation engine → two memories (semantic + episodic) → tiered reasoner.
- `.ai-factory/specs/01-23` — the existing task specs (contract-line detail) that must be reconciled against the reimagined phase intros during the merge.
- The roadmap two-tier format: a contract line in the roadmap **plus** a spec note in `.ai-factory/specs/<NN>-<slug>.md` (new specs number from **24**); atomic tasks live **above** `---STOP---`, phase backlog below. This is the editor's working grammar.

### Read on demand
- `docs/concepts/derivation-modes.md`, `docs/concepts/code-derived-understanding.md`, `docs/concepts/source-strategy-profiles.md` — the forward-looking source-strategy / code-vs-artifact / over-time model (backs Phases 15, 16, 24).
- `docs/spec/{understanding,narration,delivery,ingestion,configuration}.md` — behavioral spec the phases point at.
- `.ai-factory/handoffs/02-herald-design-and-roadmap-decompose.md` — the prior session's full design residue (rejected alternatives, spike numbers, infra creds).

## 3. Current state

**Done this session:**
- Fixed `spec 07` default source-strategy profile to the ai-factory layout (`.ai-factory/ARCHITECTURE.md`, `.ai-factory/ROADMAP.md`, `.ai-factory/specs/**`; excludes `plans`/`plan-reviews`/`reviews`/`notes`/`handoffs`/code) — it was pointing at root files and would have dropped all pruned/shipped knowledge. **Bug fix, not a feature.**
- Formalized the "two engines" in `docs/architecture.md`: event stream + derivation engine + reasoner + two memories; seams table gained **Episodic store**, `Narrator`→`Reasoner`; section heading + anchor changed to `#the-two-engines-over-the-event-stream`. Propagated the ref + anchor into `code-derived-understanding.md` and `source-strategy-profiles.md`.
- Re-studied mempalace + graphify under the new lens (via Explore agents): content-level temporal memory is nobody's free lunch; model-swap seam pattern confirmed; Postgres/pgvector + one-store cross-project validated; text-only limitation noted.
- Wrote the reimagined `## Herald reimagined` outline (Phase 13–26) below the final `---STOP---` in `ROADMAP.md`.
- Created `docs/concepts/derivation-modes.md` (richness spectrum, three trajectories, per-historical-tree profile eval, code/artifact coexistence, crossed with two memories) + pointer from `code-derived-understanding.md`.

**In-flight:**
- The **merge itself** — Phase 13–26 (bottom) → Phase 1–12 (top). Not started.

**Uncommitted working-tree state:**
- None. Everything is committed at `7336c6b` ("Roadmap update"), `dev` ahead of origin (not pushed).

## 4. Next step
The **architect** (user) instructs, in English, which merge move to make first; the **editor** (you) executes it on `.ai-factory/ROADMAP.md`. The end state: **no ephemeral Phase 13–26 left at the bottom**, the top phases absorb the new tasks, get reordered (conversation-core before broadcast), and reflect the new model. Do **not** unilaterally restructure — wait for the architect's specific instruction, edit, then the architect validates (possibly a second parallel stream — "three heads better than two").

## 5. Working discipline
- **Roles:** user = **architect** (instructs in English, validates every edit); you = **roadmap editor** (process the roadmap on instruction). Every edit is checked before it stands.
- **Draft-then-confirm on judgment; execute immediately on unambiguous directives** ("делай", "сделай", "поехали", "слей").
- **Commit only on explicit request** — the user runs `/command-commit-roadmap-update` (commits all as `Roadmap update`; amends if the last commit is an unpushed `Roadmap update`). Never auto-commit, never push.
- **Plan-only:** chat plans and writes planning artifacts/docs; the orchestrator implements app code in a separate run. Do not touch `src/`.
- The user rewards honest pushback, dislikes sycophancy and duplication ("one home per fact"), and steers by in-the-moment correction.

## 6. Error log
- **`spec 07` profile pointed at root `ARCHITECTURE.md`/`ROADMAP.md`** — ai-factory keeps these under `.ai-factory/`, so the profile would have missed all pruned/shipped knowledge. Fixed to select the `.ai-factory/` layout + `specs/**`, exclude transient dirs. If touching source-strategy tasks in the merge, keep this fix.
- **Framed the memory fork wrong** ("bitemporal vector store vs mempalace split") — the architect corrected: **RAG is an access lens, not a store type**; both memories (semantic + episodic) are retrievable. The store split is current-state vs history, not vector vs flat. Recorded in `architecture.md`.

## 7. Orientation
- **Two `---STOP---` markers** in `ROADMAP.md`: after Phase 10's tasks, and at the very end after Phase 26. The merge dissolves the bottom (Phase 13–26) block.
- **Two roadmaps coexist in the file right now:** top = real decomposed Phase 1–12; bottom = reimagined Phase 13–26 outline. Reimagined numbering continues at 13+ **only to avoid collision**; on merge/promotion, renumber into the top's sequence.
- **Two "engine" names, mid-migration:** `architecture.md` now says **derivation engine** + **reasoner**; the top ROADMAP phase headers and specs still say **"Knowledge engine" (Phase 3)** / **"Changelog engine" (Phase 5)**. This naming drift is **known and not yet propagated** — the merge is where it gets reconciled.
- **Two spec dirs:** `.ai-factory/notes/01-07` (Phase 1) vs `.ai-factory/specs/01-23` (Phase 2–10). New specs continue from **24**.
- **Two ARCHITECTURE docs:** `.ai-factory/ARCHITECTURE.md` (code-organization pattern) vs `docs/architecture.md` (domain). Never merge them.
- **Anchor changed:** `#two-engines-over-one-source-strategy` → `#the-two-engines-over-the-event-stream` (all refs updated; don't reintroduce the old one).

## 8. Domain model spine (settled — don't re-litigate)
- **Event stream is the source of truth**; **semantic memory** = snapshot of what a project *is now*, **episodic memory** = append-only log of *how it changed* (removed work stays recoverable); both retrievable. (`docs/architecture.md#the-two-engines-over-the-event-stream`)
- **Derivation engine writes both memories; reasoner reads both.** Reasoner is tiered/swappable — free local / paid hosted over the **same** knowledge base; **the embedder is fixed per store** (a model swap must never fork the index). (`docs/architecture.md`, `docs/spec/narration.md#the-llm-boundary`)
- **Conversation is the core; broadcast (the herald) is one projection** of the same reasoner — sequenced after the core, reversing the old delivery-first order. (`ROADMAP.md` reimagined preamble)
- **Derivation mode follows harness richness, evaluated per historical tree**; richness (none/poor/rich) sets the semantic *source* (code↔artifacts) and the episodic *intent-anchoring* strength (commit-msg↔roadmap-task). Code-derived and artifact-derived coexist along one timeline. (`docs/concepts/derivation-modes.md`)
- **Code is never embedded raw** — code-only repos get a one-time, human-reviewed distillation bootstrap into feature-level artifacts. (`docs/concepts/code-derived-understanding.md`)
- **Postgres/pgvector is sufficient** for the code domain — commit counts are small (mind_api 457, tradeoxy_core 450, tradeoxy_broker 671; ecosystem ≈ low thousands → ~30k vectors, orders of magnitude under pgvector's comfort zone). The real cost is **embedding compute during history backfill**, not storage. Biodata (Mind) is a **seam swap** to a time-series backend, not a Postgres concern. (chat residue — not in any doc)
- **Cross-project via retrieval + graph, no surface heuristic**; mirror is a generic full clone, selection lives in the source strategy. (`docs/spec/understanding.md`)

## 9. Hard rules
- Commit only on explicit permission; never push unless told. English for all artifacts; Russian in chat. Plan-only — no `src/` edits. Two-tier + Atomicity Gate for tasks; above-`---STOP---` = orchestrator-ready; new specs number from 24. Memory writes only on an explicit trigger phrase.

## 10. Cross-cutting contracts / invariants for the merge
- **Reconcile engine names:** propagate `Knowledge engine`→derivation / `Changelog engine`→reasoner where the merge touches Phase 3/5 headers and specs, or consciously decide to keep the old phase labels — but don't leave `architecture.md` and the roadmap contradicting silently.
- **Episodic memory is NEW** — specs `01-23` cover only the old semantic-snapshot + narration + delivery. The merge must **introduce episodic-memory tasks** (Phase 16) with no existing spec to inherit.
- **Conversation surface (Phase 19) is NEW** — no specs exist; net-new tasks.
- **Tiered-reasoner entitlement** (free local / paid hosted) lands in the multi-tenant phase (26); the seam is designed earlier but the entitlement wiring is late.
- **The linked-change resolver (`spec 11`) is the trickiest straddle** — under the new model it is effectively the **episodic-memory writer** (intent→change→outcome), not just a changelog input. Watch this when splitting old Phase 5 across new Phases 16/18/20.

## 11. Per-unit map with watch-points (reimagined phase → old material)
- **13 Ingestion & event stream** ← old Phase 2 (specs 01-03). Straightforward carry-over.
- **14 Repo mirror** ← old 3.1 (spec 04). Carry-over; keep it generic (no per-project policy).
- **15 Semantic memory** ← old Phase 3 (specs 05-08). Watch: `spec 07` profile was just fixed to ai-factory layout.
- **16 Episodic memory** ← **NEW, no spec.** Reuses `spec 11`'s linked-change idea as the writer. Highest-risk unit.
- **17 Project graph & cross-project** ← old Phase 4 + 6.1 (specs 09,10,13). Neighbor discovery = retrieval + graph, no heuristic.
- **18 Reasoner** ← old 5.2 narrator generalized (spec 12) + the LLM boundary. Watch: this is the tiered/swappable seam.
- **19 Conversation** ← **NEW, no spec.** The core product; net-new.
- **20 Narration & delivery (broadcast projection)** ← old Phase 5+6+7 (specs 11,12,13,14,15,16). Watch the `spec 11` split with Phase 16.
- **21 Weekly digest** ← old Phase 8 (specs 17-18).
- **22 Releases & versioning** ← old Phase 9 (specs 19-21).
- **23 Changelog channel** ← old Phase 10 (specs 22-23). Our-side-only, verified against a stub.
- **24 Code-derived understanding** ← **NEW concept** (`derivation-modes.md` + `code-derived-understanding.md`), gated on a first no/poor-harness repo (Tradeoxy).
- **25 Production deployment** ← old Phase 11.
- **26 Multi-tenant, entitlements & GUI** ← old Phase 12 + the reasoner-tiering entitlement wiring.
