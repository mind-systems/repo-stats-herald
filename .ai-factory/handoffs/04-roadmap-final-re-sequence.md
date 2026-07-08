# Handoff — roadmap-final-re-sequence

## 1. Frame
Herald's roadmap merge is complete — a 14-phase "reimagined" plan (phases 13–26) was folded, phase by phase, into the active decomposed roadmap, leaving one active/backlog split whose active phase numbers are in reimagined *execution order* but out of *numeric* order; the one remaining task is the **final re-sequence**: renumber to a clean monotonic sequence and sweep every spec-internal cross-reference. The originating session's context isn't available here — trust these files, not memory.

## 2. Read-first map

### Must-read now (minimal rehydration set)
- `.ai-factory/handoffs/architect-buffer.md` — **the single best entry doc.** The architect's private clipboard: it holds the re-sequence plan, the exact current NON-MONOTONIC active order, the known stale spec-internal refs to sweep, and the "relocate only when execution order forces it" discipline. Read it first. (It is private to the architect — see Hard rules — but you, as the re-sequence editor working under the architect, are being pointed to it deliberately.)
- `.ai-factory/ROADMAP.md` — the file you renumber. One `---STOP---`: atomic orchestrator-ready tasks above it, backlog below. Read the whole thing — phase headers, task numbers (`N.M`), and every intra-line cross-ref (`depends on N.M`, `Phase N`, `X.Y's`).
- `docs/architecture.md` (section **The two engines over the event stream**) — *why* the phase order is what it is: event stream → derivation engine → two memories (semantic + episodic) → tiered reasoner → narration & conversation as projections. The execution order encodes these dependencies; the renumber must preserve them.

### Read on demand
- `.ai-factory/specs/01–39` — the per-task spec notes you sweep for internal `Phase N` / `N.M` prose. **Referenced by FILENAME, never by task number** — renumbering tasks renames no spec files; only the prose inside each spec, and the ROADMAP numbers, change. Read a spec down to the docs/code it names before rewiring a reference to it (grounding discipline, §5).
- `docs/spec/{ingestion,understanding,narration,delivery,configuration,conversation}.md` — the behavioral spec each phase realizes; the "language of the docs" to match.
- `docs/concepts/{source-strategy-profiles,code-derived-understanding,derivation-modes}.md` — forward-looking design (the deferred plugin registry, code-derivation).
- `.ai-factory/handoffs/03-merge-reimagined-roadmap-phases.md` — the prior handoff; the merge's starting map (numbers now advanced past it).

## 3. Current state

**Done:**
- The entire reimagined→active merge (phases 13–26 all dissolved). The file is back to one active section + one backlog, one `---STOP---`.
- 39 task specs (`.ai-factory/specs/01–39`) + the domain docs. Superseded work kept as record with `> SUPERSEDED …` first-line markers (specs 12 narrator, 13 NeighborFinder, 14 forest).
- Committed at `483a9f8` ("Roadmap update") on `dev`; branch is ahead of origin, **not pushed**.

**In-flight:**
- The **final re-sequence** — not started.

**Uncommitted working-tree state:**
- None (everything is committed at `483a9f8`).

## 4. Next step
Do the **final re-sequence** of `.ai-factory/ROADMAP.md`. Two moves, in one deliberate pass:
1. **Renumber** the non-monotonic active phases to a clean monotonic execution order. Current active order (top→bottom, the order the orchestrator already runs by position): `1, 2, 3, 16, 24, 4, 18, 20, 7, 8, 9, 10`. A clean target is `1..12` in that same running order — i.e. `16→4, 24→5, 4→6, 18→7, 20→8, 7→9, 8→10, 9→11, 10→12`; renumber each phase's tasks to match (`16.1→4.1`, …). Backlog below the stop: `11, 12, 25` → continue the sequence (`11→13 prod, 12→14 multi-tenant, 25→15 conversational surface`). These are a suggestion — the architect confirms the exact scheme; do not renumber unilaterally without the prompt.
2. **Sweep every cross-reference** so no dangling number survives: intra-ROADMAP `depends on N.M` / `Phase N`, and each spec's internal `**Phase:** N` line and `N.M` prose. Spec FILES are not renamed (filename refs are stable). Fix the known stragglers the buffer lists (engine-naming wording like "changelog engine" in spec 17; spec 03's "Phases 7/10" forward-refs → phase-name; and any `Phase 26`→`Phase 12` tiering refs already partly done).

This runs as a prompt from the architect; you apply and report the diff; the architect verifies by fact and only then commits.

## 5. Working discipline
- **Two-editor validation loop.** The architect (the user's counterpart) drafts an instruction as an English fenced ```text block; you (the editor) apply it exactly and report a summary + diff; the architect then **verifies by fact** — `grep`/`read` the actual files, never trusts the editor's word alone. Expect your work to be independently re-checked. Report honestly (flag anything you couldn't do or did beyond scope).
- **Read down the reference chain — don't be lazy with the doc tree.** Ground every action in the leaf, not the description of it: a ROADMAP task line names its `Spec:` note; that note names the docs/code it touches. Before you rewire a reference to a spec, open that spec (and what it names) and confirm the target by fact. A named spec or doc that you don't open is a reference you're guessing at.
- **Confirm before executing; verify after.** No unilateral restructuring — apply the architect's prompt as written, no more. If the prompt's numbering would collide or drop a ref, stop and say so rather than improvising.
- **Commit only when told** — never auto-commit or push.

## 6. Error log
- **Destroy-and-restore of the conversation tasks.** The architect said "move the conversation layer to a backlog phase"; the prompt mis-translated "backlog" as "convert to prose", so the editor **deleted** the decomposed task contract lines (removed Phase 19 with tasks 19.1/19.2, removed 7.3 from Phase 7) and added `> DEFERRED` markers to specs 29/37/38. That destroyed finished decomposition. **Correction:** restored the three tasks *decomposed* as `### Phase 25 — Conversational surface` **below** the stop (25.1 endpoint/spec 29, 25.2 multi-turn/spec 37, 25.3 Telegram-inbound/spec 38), DEFERRED markers removed, cross-refs re-pointed. **Lesson: "move to backlog" ≠ "demote to prose" — reposition ready tasks, keep them decomposed.**
- **Phantom "app-languages gap".** The architect flagged a gap (release note couldn't produce an app's languages), then *conceded* it wasn't a gap because the frozen changelog contract hardcoded `summary_ru`/`summary_en?`. The user rejected the hardcode itself. **Correction:** de-hardcoded the contract to a `summaries: {lang: text}` map (spec 22, spec 20 `build(...,langs)`, spec 23, `docs/spec/delivery.md`). **Lesson: challenge a hardcode, don't defer to it.**
- **Cross-ref leak from incremental renumbering.** Renumbering the narrator `5.2→5.1` (Phase 16 merge) left stale `5.2` refs in specs 14/17/20, caught rounds later; likewise a proposed relocation of neighbor discovery (6.1) would have leaked `6.1` refs into specs 17/20. **Lesson (now a rule):** relocate/renumber a task ONLY when execution order forces it; do the comprehensive cross-ref sweep **once**, here, at re-sequence — which is exactly why this pass exists.

## 7. Orientation
- **Non-monotonic active numbers are intentional.** Phase headers read `1, 2, 3, 16, 24, 4, 18, 20, 7, 8, 9, 10` — reimagined execution order, out of numeric order. The orchestrator runs by *file position*, so it already works; the re-sequence is the readability + consistency cleanup.
- **A backlog phase with DECOMPOSED tasks.** `Phase 25 — Conversational surface` sits *below* the stop but carries full tasks (25.1–25.3), not prose — unusual, deliberate: conversation is ready but deferred by position until promoted above the stop. Don't "fix" it into prose.
- **Two ARCHITECTURE docs:** `.ai-factory/ARCHITECTURE.md` (code-organization pattern) vs `docs/architecture.md` (domain model). Never conflate.
- **Two spec dirs:** `.ai-factory/notes/01–07` (Phase 1's notes) vs `.ai-factory/specs/01–39` (Phase 2+). New specs continue from 40.
- **Specs are referenced by filename, not task number** — the safety net that makes renumbering tractable.
- **Two meanings of "engine"** were reconciled to **derivation engine** + **reasoner** (`docs/architecture.md`); leftover "changelog/knowledge engine" wording inside specs is a sweep target, not a live concept.

## 8. Domain model spine (settled — don't re-litigate)
- **Event stream = source of truth; two memories:** semantic (what a project *is now*, the pgvector `KnowledgeStore`) + episodic (how it *changed*, append-only `EpisodicStore`); both retrievable — RAG is an access *lens*, not a store type. (`docs/architecture.md#the-two-engines-over-the-event-stream`)
- **Derivation engine writes both memories; the reasoner reads both.** The reasoner is tiered/swappable (free local / paid hosted over the *same* base); **the embedder is fixed per store** so one query embedding retrieves from both. (`docs/spec/narration.md#the-llm-boundary`, `docs/spec/conversation.md`)
- **Conversation is the core; narration/broadcast is one projection of the same reasoner.** (`docs/spec/conversation.md`)
- **Code-derived understanding is a *derivation mode*, not a blocker** — a concrete code source-strategy + distillation + one-time reviewed bootstrap feeding the same memories (Phase 24 / specs 32–35). The **general plugin registry** (auto-detect + N profiles) stays deferred — two concrete profiles + configured selection suffice. (`docs/concepts/source-strategy-profiles.md`, `code-derived-understanding.md`, `derivation-modes.md`)

## 9. Hard rules
- **Commit only via `/command-commit-roadmap-update`** → message `Roadmap update` (amends an unpushed `Roadmap update`, else new). Never auto-commit, never push.
- **All artifacts in English** (chat is Russian; artifacts English).
- **`architect-buffer.md` is PRIVATE to the architect** — in normal operation the editor must never read, touch, or reference it. (This handoff points you at it only because the re-sequence *is* the architect-owned plan it holds.)
- **Spec files by filename; relocate/renumber only when execution order forces it.**
- Plan-only: the roadmap/specs are planning artifacts; the orchestrator implements code in a separate run — do not touch `src/`.

## 10. Cross-cutting contracts / invariants checklist
Keep these identical everywhere while renumbering — they are the recurring names the sweep must not corrupt:
- **Seams:** `KnowledgeStore` (semantic), `EpisodicStore` (episodic, append-only, `changed_at` ≠ `recorded_at`), `Reasoner`, `Localizer`/`Translator`, `ProjectGraph`, `SourceStrategy` (+ `CodeSourceStrategy`), `LLMClient`, `Embedder`, `TelegramClient`, `ChangelogClient`, `GitHubReleaseClient`, `RepoMirror`, `GitHubAppAuth`.
- **Reasoner methods:** `answer(query, repo)` [conversation], `narrate(change, lang="ru")` [broadcast], `narrate_weekly(change, open_tasks)` [weekly]. `narrate` is the single native-generation primitive; localization is a strategy *around* it.
- **Localization:** `Localizer.notes(change, langs) -> dict[lang,str]`; `PivotLocalizer` (canonical-pivot, the shipping default) + `NativeLocalizer`; `Translator` seam (LLM today, swappable). Callers ask only `notes(...)`, never know the strategy.
- **Changelog contract (de-hardcoded):** entry `{version, environment, summaries:{<lang>:<text>}, github_url}` — a language-keyed map, NO `summary_ru`/`summary_en?`. `ReleaseNote.build(repo, org_id, branch, langs)` produces exactly the given languages. (`contract/changelog.openapi.yaml`, `docs/spec/delivery.md#internal-protocol`)
- **`LinkedChange.resolve` is resolved ONCE per push** (shared by the episodic writer and narration — resolve-once, not per consumer).
- **`NeighborFinder`/forest are retired** — cross-project reach lives inside the reasoner (its `answer`/`narrate` fold in `ProjectGraph.neighbors` + org-wide retrieval directly).

## 11. Per-unit map with watch-points
Active section (current № → what it is / reimagined origin → watch-point during renumber):
- **1 — Summarizer spike & eval harness** — done (`[x]`, specs in `.ai-factory/notes/`). The eval harness (`evals/`) is reused by code-distillation's verify (spec 33).
- **2 — Ingestion & the event stream** (←13). Tasks 2.1–2.4; 2.4 (installation-repositories) is new. `2.3` delivery-plan resolver placement is still provisional (buffer: keep-vs-move to broadcast is open — decide during re-sequence). spec 03 has stale "Phases 7/10" forward-refs to sweep.
- **3 — Repo mirror & semantic memory** (←14+15 folded). Tasks 3.1–3.5. Two-paragraph intro (mirror substrate; then semantic memory). `3.4` source-strategy profile is the ai-factory layout (fixed this session).
- **16 — Episodic memory** (←16, net-new, inserted after 3). Tasks 16.1–16.4. **Watch:** `16.2` is the linked-change resolver *relocated* from old `5.1`/spec 11 (episodic owns it; narration consumes it) — its refs must stay pointed at episodic after renumber.
- **24 — Code-derived understanding** (←24, net-new, after 16). Tasks 24.1–24.4; `24.4` extends `16.4`'s backfill (per-historical-tree code vs artifact) — keep that dependency intact.
- **4 — Project graph & the cross-project surface** (←17). Tasks 4.1–4.2. `6.1` NeighborFinder retired (spec 13 SUPERSEDED); nothing active should reference it.
- **18 — The reasoner over both memories** (←18, net-new). Tasks 18.1 (reasoner core: retrieval + `answer`) + 18.2 (cross-project reach). Narration reuses 18.1/18.2's retrieval, not `answer`.
- **20 — Narration (the broadcast projection)** (←20, net-new; superseded old 5.1 narrator + 6.1/6.2). Tasks 20.1 (`Reasoner.narrate`, gained `lang`) + 20.2 (Localizer/Translator). Old delivery stays in Phase 7 (delivery reorg deferred to *this* re-sequence — see buffer 2.3).
- **7 — Delivery & routing.** Tasks 7.1, 7.2 (7.3 moved to Phase 25). 7.2 goes through `Localizer.notes`.
- **8 — Weekly digest cadence** (←21). Tasks 8.1–8.3; 8.3 (weekly localization) is new; 8.1 rewritten onto the reasoner (`narrate_weekly`).
- **9 — GitHub releases & versioning** (←22). Tasks 9.1–9.3; 9.2 rewritten (`build(...,langs)` via Localizer, no NeighborFinder); 9.3 resolves the language union once.
- **10 — Internal protocol (changelog channel)** (←23). Tasks 10.1, 10.2; de-hardcoded `summaries` map.

Backlog (below stop):
- **11 — Production deployment** (←25 folded): Docker beside Ollama, pgvector image.
- **12 — Multi-tenant, entitlements & GUI** (←26 folded): adds the entitlement tiering (free local / paid hosted, embedder fixed) + per-app keys.
- **25 — Conversational surface** — DECOMPOSED (25.1 endpoint, 25.2 multi-turn, 25.3 Telegram-inbound); ready to promote above the stop when conversation is prioritized. The reasoner (Phase 18) is its built foundation (`answer` exists but is unexposed until this ships).
