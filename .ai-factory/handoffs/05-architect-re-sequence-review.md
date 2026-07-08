# Handoff — architect-re-sequence-review

## 1. Frame
You are the ARCHITECT who spent this session reframing Herald and merging its 14-phase "reimagined" roadmap (phases 13–26) into the active decomposed roadmap; the merge is done and one task remains — the **final re-sequence** (renumber the non-monotonic active phases + sweep every cross-ref) — which the EDITOR does and you DRIVE and REVIEW BY FACT. The originating session's context isn't available here; trust these files, not memory.

## 2. Read-first map

### Must-read now (minimal rehydration set)
- `.ai-factory/handoffs/architect-buffer.md` — **your own private clipboard; lead here.** Holds the re-sequence plan, the exact current NON-MONOTONIC active order, the known stale spec-internal refs to sweep, and the disciplines. You read AND edit this file directly (the only file you touch directly); the editor never sees it.
- `.ai-factory/handoffs/04-roadmap-final-re-sequence.md` — **the editor's handoff (what the fresh editor is told to do).** Your review checks the editor's output against this; it also carries the full per-phase map and read-tree.
- `.ai-factory/ROADMAP.md` — the file being renumbered; read every phase header, task `N.M`, and intra-line cross-ref.
- `docs/architecture.md` (section **The two engines over the event stream**) — the model the phase order encodes (event stream → derivation → two memories → tiered reasoner → narration/conversation projections); the renumber must preserve these dependencies.

### Read on demand
- `.ai-factory/specs/01–39` — swept for internal `Phase N`/`N.M` prose; **referenced by FILENAME, never task number** (renumbering renames no spec files). Read a spec down to what it names before trusting a rewired ref.
- `docs/spec/{ingestion,understanding,narration,delivery,configuration,conversation}.md` — behavioral spec per phase.
- `docs/concepts/{source-strategy-profiles,code-derived-understanding,derivation-modes}.md` — forward-looking design (deferred plugin registry, code-derivation).
- `.ai-factory/handoffs/03-merge-reimagined-roadmap-phases.md` — the merge's start-state (numbers now advanced).

## 3. Current state

**Done:**
- The whole reimagined→active merge (13–26 all dissolved). `.ai-factory/ROADMAP.md` is one active section + one backlog, one `---STOP---`.
- 39 task specs; superseded work kept with `> SUPERSEDED …` markers (specs 12 narrator, 13 NeighborFinder, 14 forest).
- Two prior handoffs written this session (`04` for the editor, this `05` for you).
- Committed at `483a9f8` ("Roadmap update") on `dev`; ahead of origin, **not pushed**.

**In-flight:**
- The **final re-sequence** — not started. You draft the prompt; the editor applies; you review.

**Uncommitted working-tree state:**
- None at `483a9f8`. (After you write `04`/`05` this session, they are untracked until the next `/command-commit-roadmap-update`.)

## 4. Next step
**(a) Draft the re-sequence prompt** for the editor (English fenced ```text block) from `architect-buffer.md`'s plan: renumber the active phases — current running order `1, 2, 3, 16, 24, 4, 18, 20, 7, 8, 9, 10` → clean `1..12` in that SAME order (`16→4, 24→5, 4→6, 18→7, 20→8, 7→9, 8→10, 9→11, 10→12`, tasks `N.M` to match); backlog `11, 12, 25` → continue (`11→13, 12→14, 25→15`); and sweep every cross-ref (intra-ROADMAP `depends on N.M`/`Phase N`, each spec's `**Phase:** N` + `N.M` prose, the named stragglers). Instruct: spec FILES are NOT renamed; keep `Phase 25`'s decomposed tasks (do not demote to prose); resolve the open 2.3 delivery-plan-resolver keep-vs-move.

**(b) After the editor reports, VERIFY BY FACT** — the review checklist:
- Active phases now monotonic `1..12`, same running order as before.
- Every task renumbered (`16.1→4.1`, …); grep the OLD phase numbers used as refs (`\b16\b \b24\b \b18\b \b20\b` in phase/task context) → none dangling.
- Each spec's `**Phase:** N` line + internal `N.M` refs updated; grep specs for stale old numbers.
- Spec FILES unchanged in name (only content); superseded markers on specs 12/13/14 intact.
- Backlog `Phase 25` still carries `25.x`-renumbered decomposed tasks below the stop.
- Named stragglers gone: "changelog engine" wording (spec 17), spec 03 "Phases 7/10" forward-refs, any `Phase 26`→`Phase 12` tiering ref.
- Only ROADMAP numbers + spec-internal prose changed — no seam names, contracts, or logic touched.

## 5. Working discipline (architect's side)
- **Two-editor validation loop.** You draft an instruction as an English fenced ```text block; the editor applies it exactly and reports a summary + diff; you then **verify by fact** — `grep`/`read` the real files, never the editor's word. Two independent heads catch what one misses.
- **You edit only `architect-buffer.md` directly.** Every ROADMAP/spec change goes through the editor via a prompt. (This session you also authored the domain docs `docs/architecture.md`, `docs/spec/conversation.md`, a `docs/spec/narration.md` paragraph — architect-authored docs are your lane; task specs are the editor's.)
- **Read down the reference chain to the leaf.** A task line names its `Spec:` note; the note names docs/code; open them, confirm by fact — never rewire a reference you haven't opened.
- **Confirm before execute; commit only when told.** Draft → user approves → editor applies → you verify → user runs the commit command. Never auto-commit or push.

## 6. Error log
- **Destroy-and-restore of the conversation tasks.** You mis-translated the user's "move the conversation layer to a backlog phase" into a prompt that told the editor to CONVERT it to prose — the editor deleted decomposed task lines (Phase 19 + tasks, 7.3) and added `> DEFERRED` spec markers. **Fix:** restored them decomposed as `### Phase 25 — Conversational surface` below the stop (25.1/25.2/25.3), markers removed. **Lesson: "move to backlog" ≠ "demote to prose" — reposition ready tasks, keep them decomposed.** (Directly relevant: during re-sequence, Phase 25 must stay decomposed.)
- **Phantom app-languages gap.** You flagged a gap, then *conceded* it because the changelog contract hardcoded `summary_ru`/`summary_en?`. The user rejected the hardcode itself. **Fix:** de-hardcoded to a `summaries:{lang:text}` map (specs 20/22/23 + `docs/spec/delivery.md`). **Lesson: challenge a hardcode, don't defer to it.**
- **Cross-ref leaks — the reason the re-sequence exists.** Incremental renumbering leaked stale refs (`5.2→5.1` left stragglers in specs 14/17/20; a proposed `6.1` relocation would have leaked into 17/20). **Discipline:** relocate/renumber ONLY when execution order forces it; do the comprehensive cross-ref sweep ONCE, at re-sequence. Your review's whole point is to confirm no such leak survives.

## 7. Orientation
- **Non-monotonic active numbers are correct as-is** (reimagined execution order); the orchestrator runs by file position. The re-sequence is cleanup, not a fix.
- **A backlog phase with DECOMPOSED tasks** — `Phase 25` below the stop carries tasks, not prose. Deliberate; don't let the re-sequence flatten it.
- **Two ARCHITECTURE docs:** `.ai-factory/ARCHITECTURE.md` (code pattern) vs `docs/architecture.md` (domain). **Two spec dirs:** `.ai-factory/notes/01–07` (Phase 1) vs `.ai-factory/specs/01–39`. **Two "engine" meanings** reconciled to derivation-engine + reasoner (leftover "changelog engine" wording in specs is a sweep target).
- **Specs referenced by filename, not number** — the safety net making renumber tractable.

## 8. Domain model spine (settled — do not re-litigate)
- **Event stream = source of truth; two memories:** semantic (`KnowledgeStore`, what is now) + episodic (`EpisodicStore`, how it changed, append-only); both retrievable — RAG is an access *lens*. (`docs/architecture.md#the-two-engines-over-the-event-stream`)
- **Derivation engine writes both; reasoner reads both;** tiered/swappable (free local / paid hosted, same base); **embedder fixed per store** (one query embedding hits both memories). (`docs/spec/narration.md#the-llm-boundary`)
- **Conversation is core; narration is one projection of the same reasoner.** (`docs/spec/conversation.md`)
- **Code-derived is a derivation MODE** (concrete code source-strategy + LLM distillation + one-time reviewed bootstrap → same memories; Phase 24). **The general plugin registry stays DEFERRED** — two concrete profiles + configured selection suffice. (`docs/concepts/*`)
- **Changelog contract is a language-keyed `summaries` map** — no RU/EN hardcode; any language via the Localizer/Translator seam. (`docs/spec/delivery.md#internal-protocol`)

## 9. Hard rules
- **Commit only via `/command-commit-roadmap-update`** → `Roadmap update`; never auto-commit/push.
- **English artifacts** (chat Russian, artifacts English).
- **Buffer ownership:** you edit `.ai-factory/handoffs/architect-buffer.md` directly; the editor must never read/touch it; all other edits go through the editor.
- **Spec files by filename; relocate/renumber only when execution order forces it.**
- Plan-only — no `src/` edits (the orchestrator implements separately).

## 10. Cross-cutting contracts / invariants + grep-checklist
Names that must stay identical through the renumber (the sweep changes numbers, never these):
- **Seams:** `KnowledgeStore`, `EpisodicStore` (`changed_at`≠`recorded_at`), `Reasoner`, `Localizer`/`Translator`, `ProjectGraph`, `SourceStrategy`/`CodeSourceStrategy`, `LLMClient`, `Embedder`, `TelegramClient`, `ChangelogClient`, `GitHubReleaseClient`, `RepoMirror`, `GitHubAppAuth`.
- **Reasoner methods:** `answer(query, repo)` [conversation], `narrate(change, lang="ru")` [broadcast], `narrate_weekly(change, open_tasks)` [weekly] — `narrate` is the single native-generation primitive.
- **Localization:** `Localizer.notes(change, langs)→dict[lang,str]`; `PivotLocalizer` (default) + `NativeLocalizer`; `Translator` swappable.
- **Changelog:** entry `{version, environment, summaries:{<lang>:<text>}, github_url}`; `ReleaseNote.build(repo,org_id,branch,langs)`.
- **`LinkedChange.resolve` once per push** (shared by episodic writer + narration).
- **`NeighborFinder`/forest retired** — cross-project reach lives in the reasoner.

Post-re-sequence grep-checklist (run each; expect the OLD numbers gone from ref-context):
`grep -nE "^### Phase " ROADMAP.md` (monotonic 1..12 + backlog); `grep -rnE "\bPhase (16|24|18|20)\b" .ai-factory/specs/` (stale phase refs); `grep -rnE "depends on 1[68]|2[04]" .ai-factory/specs/` (stale task refs); `grep -rn "changelog engine\|knowledge engine" .ai-factory/specs/`; `grep -rn "summary_ru\|summary_en" .` (must be zero); `ls .ai-factory/specs/` (filenames unchanged); confirm `Phase 25` block still has `- [ ] **25` task bullets below the stop.

## 11. Per-unit map with watch-points
(Full per-phase detail is in `04-roadmap-final-re-sequence.md §11`; here, the audit lens.)
Active (current № → origin → re-check on renumber):
- **1** summarizer (done) — untouched.
- **2** ingestion (←13) — 2.1–2.4; **2.3** resolver keep-vs-move still open (decide in the re-sequence prompt); spec 03 stale "Phases 7/10".
- **3** mirror & semantic (←14+15) — 3.1–3.5; two-paragraph intro.
- **16** episodic (←16, net-new) — 16.1–16.4; **16.2 is the relocated linked-change resolver** (spec 11) — after renumber it must still read as episodic-owned, narration-consumed.
- **24** code-derived (←24, net-new) — 24.1–24.4; **24.4 extends 16.4's backfill** — keep that dependency after both renumber.
- **4** project graph (←17) — 4.1–4.2; **6.1 NeighborFinder retired** (spec 13 SUPERSEDED) — nothing active may reference it.
- **18** reasoner (←18, net-new) — 18.1–18.2; narration reuses its retrieval, not `answer`.
- **20** narration (←20, net-new; superseded old 5.1/6.1/6.2) — 20.1 `narrate`, 20.2 Localizer/Translator.
- **7** delivery — 7.1, 7.2 (7.3 moved to Phase 25); 7.2 via Localizer.
- **8** weekly (←21) — 8.1–8.3; 8.1 on the reasoner, 8.3 localization.
- **9** releases (←22) — 9.1–9.3; 9.2 `build(...,langs)`, 9.3 resolves the language union once.
- **10** changelog channel (←23) — 10.1, 10.2; `summaries` map.
Backlog (below stop):
- **11** prod (←25) · **12** multi-tenant + entitlements (←26) · **25** conversational surface — decomposed (25.1/25.2/25.3), keep below the stop, promotable; the reasoner (18) is its built foundation.
