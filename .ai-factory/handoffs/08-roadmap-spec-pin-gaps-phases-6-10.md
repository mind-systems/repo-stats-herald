# Handoff — Roadmap spec pin-gaps, Phases 6–10 (+ docs restructure, two rescues, two concepts)

## 1. Frame
Herald (repo-stats-herald) — a planning/chat session that ran `/command-pin-gaps` and `/task-rescue` over the `.ai-factory` roadmap and its task specs, sweeping Phases 6→10 to close "fantasy holes" ahead of implementation; the originating session's context isn't available here — trust these files, not memory.

## 2. Read-first map

The next step is **pin-gaps on Phase 11** (GitHub releases & versioning), so the rehydration set is scoped to that plus the cross-cutting conventions the whole sweep enforced.

### Must-read now (minimal rehydration set)
- `.ai-factory/ROADMAP.md` — the entry; read the **Phase 11** section (its task list is the pin-gaps target) and re-skim Phases 8–10 contract lines to see the conventions the successor must keep consistent. ← lead here
- `§10` of THIS handoff — the cross-cutting contracts checklist; every Phase 11 spec must reuse these exact names/rules (bare `push.repo`, `_gather_context`, `reasoner_k`, localizer dispatch, `lang` threading, `DeliveryService`).
- `docs/behavior/delivery.md` — Phase 11's behavioral target: `#versioning` (semver from branch role, `-rc` on staging, back-merge skip) and `#internal-protocol` (the app changelog contract, Phase 12). The specs are built and verified against this.
- `.ai-factory/specs/20-release-note.md` — 11.2.x: the release note is a `Report` (`SummarySection` over a `SinceDeployWindow`), rendered per-language via `Localizer.report_notes` (10.3). Confirms the release path reuses the reporting engine, not a second mechanism.
- The pin-gaps command body (invoke `/command-pin-gaps` with the Phase 11 arg) — default-mode = edit specs in place, cite `file:line`, never invent value-hole numbers (raise under `## Blocking decisions`).

### Read on demand
- `.ai-factory/specs/21-github-release.md`, `22-changelog-protocol-client.md` — the GitHub-release cut and the internal changelog client (Phase 11/12 tasks in the sweep's path).
- `docs/behavior/configuration.md` — the resolver seam + `DeliveryPlan` fields (`is_release`/`is_prerelease`/`branch_role`) Phase 11 actually gates on.
- `docs/concepts/product-scope.md`, `docs/concepts/coordination-root-format.md` — two concept/spec docs authored this session (context for the graph/ownership model), not needed for Phase 11.
- `.ai-factory/specs/{48,27,28,30,49,31,50,17,18,39,03,15,16,10}.md` — the specs pinned this session; open the sibling of whatever Phase 11 task depends on them.

## 3. Current state

**Done:**
- Two rescues: `3.1.1` (mirror isolation single-flight) and `6.2` (coordination-root seeding), both depth-2 (spec+plan), rolled back to `planned:1` for re-implementation; convergence-audited `4.4` (healthy).
- pin-gaps closed on `7.1.1, 7.1.2, 7.2, 8.1, 8.2.1, 8.2.2, 9.1, 9.2, 9.3, 10.1.1, 10.1.2, 10.2, 10.3` (specs + contract lines synced, contract lines trimmed to the ~600 (400–1000) roadmap-engine budget).
- Docs restructure: `docs/spec/` → `docs/behavior/`, `docs/spec-overview.md` → `docs/behavior-overview.md`; all inbound links updated across live docs, README, CLAUDE.md, ROADMAP, all concepts, and all committed task specs (0 stale `docs/spec/` refs remain except intentionally-frozen handoffs).
- Two new docs: `docs/concepts/product-scope.md` (forward-looking) and `docs/behavior/coordination-root-format.md` (governing-spec of the coordination `## Coordination` member-table format).

**In-flight:**
- Phase 11 pin-gaps not started — this is the next step.

**Uncommitted working-tree state:**
- `.ai-factory/ROADMAP.md`, `.ai-factory/specs/17-weekly-digest-builder.md`, `.ai-factory/specs/39-weekly-digest-localization.md`, `.ai-factory/specs/50-digest-section-report-contract.md` — the Phase 10 pin-gaps edits, **uncommitted** on top of `7915005`. Commit them via `/command-commit-roadmap-update` before/after starting Phase 11.

## 4. Next step
Run `/command-pin-gaps` on **Phase 11 (GitHub releases & versioning)** tasks, same discipline as Phases 6–10: read each contract line + its `Spec:`-tagged task spec, ground every symbol against the actual code/collaborators (`DeliveryService`, `Report`/`SummarySection`, `Localizer.report_notes`, `DeliveryPlan`), close value/meaning holes in the spec + sync the contract line, keep it in budget, and **ask before propagating** any new cross-task convention to sibling specs. The user (max) drives task selection and approves propagations; the agent edits the specs.

## 5. Working discipline
- **Chat plans; the orchestrator implements** (global CLAUDE.md). This session only edits planning artifacts (roadmap, task specs, docs) — never `src/`/`tests/` (except a task-rescue depth-3, which was not used here). task-rescue depth-2 reverts the implementation instead.
- pin-gaps **default mode** edits the spec in place and syncs the contract line; **never invent** value-hole numbers — raise them under `## Blocking decisions` at the top of the spec with a proposed value, and wait for the user to confirm (e.g. `reasoner_k=8` was confirmed, then folded in and the Blocking section removed).
- **Propagation is ask-first:** when a pin establishes a convention a sibling task shares, propose the one-line clause and ask (options: apply / show wording / skip) before editing the sibling. The user consistently chose "apply all."
- Contract lines: roadmap-engine budget ~600 chars (400–1000); trim verbose detail to the spec, keep the line to intent + key pins. Measure with `awk 'length'` after edits.
- **Commit only** on explicit `/command-commit-roadmap-update` (amends an unpushed "Roadmap update", else new commit). Never push. Never auto-commit.
- Language: specs/roadmap/docs in **English**; chat replies to this user in **Russian**.

## 6. Error log
- **Audited the wrong task.** On the first `/task-rescue`-audit follow-up I audited the already-closed `3.1.1` instead of the in-flight task; the user corrected "заземлись об роадмап, я просил ревью текущего таска". Fix: the in-flight task was `26-4-4-historical-backfill` — always `git status --short -- .ai-factory/` and confirm the slug against the sidecar `step` before diagnosing.
- **Rename missed files.** The `docs/spec/`→`docs/behavior/` sweep first missed `docs/concepts/source-strategy-profiles.md` (caught by a verify-grep), then missed **10 committed task specs** (`02,08,20,21,22,29,36,37,42,47`) because the initial pass only covered live docs + ROADMAP. Fix: swept all `.ai-factory/specs/*.md` with `perl -pi -e 's{docs/spec-overview}{docs/behavior-overview}g; s{docs/spec/}{docs/behavior/}g;'`, then grep-verified zero leftovers. Handoffs left untouched on purpose.
- **Contract lines bloated.** pin-gaps additions pushed 6.2/7.1.1/7.2/8.1 (and later 9.3, 8.2.1) past 1000 chars; trimmed back on request (detail already lives in the specs). Watch this every pin-gaps run — add to the spec, keep the line lean.
- **Stale-note conflict is real:** the `TELEGRAM_CHANNELS = org:chat` delimited example in spec 16 contradicted the codebase (all `dict[int,str]` maps parse as JSON via `_parse_json_dict`, `config.py:26,42`). Ground map/format holes against `src/core/config.py`, not the spec's illustrative example.

## 7. Orientation
- `docs/behavior/` (the behavioral governing spec, **renamed this session** from `docs/spec/`) vs `.ai-factory/specs/` (per-task implementation specs) — the rename was *because* "spec"/"specs" collided.
- `Localizer.notes(change, langs)` (change-level, 8.2) vs `Localizer.report_notes(report, …, langs)` (report-level, 10.3) — two methods, same pivot/native dispatch.
- `Reasoner.answer` (free-text Q&A) vs `Reasoner.narrate(change, lang)` (broadcast narration) — different prompts, but they **share one internal `_gather_context(query, repo)`** retrieval+neighbor helper.
- **bare `push.repo`** vs **`org/repo`** — the recurring trap; the whole sweep enforced bare everywhere (see §10).
- `PivotLocalizer` pivot language ∈ langs vs ∉ langs — the dispatch differs (pivot is an intermediate when not requested); generalized this session.

## 8. Domain model spine
- **Reasoner retrieval is factored into one shared helper.** `_gather_context(query, repo)` (embed once → both stores → 7.2 neighbor folding); `answer` and `narrate` reuse it, differing only in the prompt after. Don't re-inline retrieval into `answer`. (`specs/27,28,30`.)
- **Per-repo stores, product is a graph/view — never a merged index.** A "product" (group of repos) unifies via the project graph + product-scoped retrieval, not a physical merge; stores stay keyed per repo. (`docs/concepts/product-scope.md`, `docs/behavior/understanding.md`.)
- **Coordination-root seeding is declaration, not guessing.** Herald reads a human-authored `## Coordination` member table (a published format) — this is the code-native "declared" path, complementary to (future) GUI declaration; `source=config` never overwritten by `source=seed`. (`docs/behavior/coordination-root-format.md`, `specs/10`.)
- **Ownership layering (forward-looking):** `tenant → product → repo`; GitHub `org`/installation is an external identity axis, not the product; "user" (OAuth login) is a tenant member, enters at the Phase 14 multi-tenant GUI; activation is project-composition (nothing runs until a repo is composed into a product), channel is per-product. (`docs/concepts/product-scope.md`.)

## 9. Hard rules
- **Commit only via `/command-commit-roadmap-update`**, never push, never auto-commit; if uncommitted changes exist, they're intentional — ask or leave.
- **pin-gaps never fabricates a value-hole number** — raise it under `## Blocking decisions`; only pin from an actual `file:line` source.
- **Handoffs and notes under `.ai-factory/` are frozen historical records** — never rewrite them (one even records "the overview file is docs/spec-overview.md… do not fix it"); the docs rename deliberately did NOT touch them.
- **Match neighbor doc language / present-tense governing-spec genre** (aif-docs): describe behavior, no change-history ("was added"/"previously"), no motivation prose; run a no-motivation grep before finalizing a doc.

## 10. Cross-cutting contracts / invariants checklist
These recur across the sweep and must stay **identical** in every Phase 11 spec that touches them:
- **Repo key = bare `push.repo`** on both endpoints of a graph `Edge` and in every `KnowledgeStore`/`EpisodicStore`/`ProjectGraph` scope — never `org/repo`. (`neighbors(repo)->list[str]` returns bare `to_repo`, `src/graph/store.py`; `Chunk.repo`/`Edge.to_repo` bare.)
- **`_gather_context(query, repo)`** — the one shared retrieval+neighbor helper; `answer`/`narrate` reuse it; 7.2 neighbor folding extends it; `narrate` consumes its *context*, does NOT call `answer`.
- **`Settings.reasoner_k = 8`** — one injected value, the SAME `k` for `KnowledgeStore.query` and `EpisodicStore.query`; reasoner reads no env directly.
- **Per-store failure isolation** — a store `query` that raises is caught per-store; degrade to the surviving store (or the no-memory / commits-only floor), never propagate. Applies to `answer`, `narrate`, and reports.
- **Localizer dispatch** (`notes` and `report_notes`): `translate` each requested lang **except the pivot** with `source_lang=pivot`; pivot returned only if itself requested; empty `langs` → empty dict, zero calls; result keys == `langs` exactly. `narrate` is the single native primitive both strategies call.
- **`lang` threaded lowercase `"ru"`** through `ReportSection.render(…, lang="ru")` → `Report.build(…, lang="ru")` → `Localizer.report_notes` → `DeliveryPlan.language`; same lowercase code `narrate`/localizer use — never `"RU"`.
- **Coordination-root format** — only the `## Coordination` member table is parsed (other tables ignored); kind from the Relationship column; atomic seed-set replace; de-classification replaces with empty. (`docs/behavior/coordination-root-format.md`.)
- **Config maps parse as JSON** via `_parse_json_dict` for `dict[int,str]` (`telegram_channels` like `github_org_logins`, `config.py:26,42`) — do NOT invent delimited formats.
- **`TELEGRAM_MESSAGE_LIMIT = 4096`** (module constant), char-boundary chunking, `join == original`, plain text (no `parse_mode`), errors via `raise_for_status` (mirror `OllamaClient`).
- **`role_for_branch`** exact-match on branch-name constants (`main`/`master`→RELEASE, `staging`→STAGING, else DEV) — case-sensitive, not prefix; comparison lives in one place.

## 11. Per-unit map with watch-points
- **task-rescue 3.1.1** (mirror isolation) → depth-2; the single-flight red test needed a `threading.Barrier(N)` in test code + a briefly-blocking `counting_mint` so it *deterministically* fails a naive per-request mint. Watch: the barrier must NOT go inside `counting_mint` (a correct single-flight calls it once → would hang).
- **task-rescue 6.2** (coordination-root seeding) → depth-2 re-implement; root cause was spec 10 never pinning the member-table format (implementer invented it; the `/`-in-name filter double-served identity + row-scope, so fixing identity broke scope). Watch: the fix lives in the published `coordination-root-format.md`; spec 10 references it, doesn't copy.
- **task-rescue-audit 4.4** → healthy convergence (independent legit fixes), no action. Watch: the O(N) embed/subprocess perf deferred-observation was pinned to **5.4**, not 4.4.
- **7.1.1/7.1.2** (reasoner contract/core) → added a 4th invariant (per-store failure isolation) + the `_gather_context` factoring + `reasoner_k=8`. Watch: spec 48 originally used `repo="o/r"` — fixed to bare.
- **7.2** (cross-project reach) → neighbor set = union(distinct `Chunk.repo`, `neighbors(repo)`) deduped, reuse one embedding + k, semantic-only neighbors. Watch: `neighbors` is directed (outgoing only).
- **8.1 narrate** → query from `completed_tasks` + `change.commits` messages; `change.commits` is the always-available floor (never empty). Watch: it consumes `_gather_context` context, does not call `answer`.
- **8.2.1/8.2.2** (localization) → generalized the pivot dispatch (pivot ∉ langs, empty langs, `source_lang=pivot`). Watch: a non-`en` pivot silently mistranslated from `en` before this.
- **9.1/9.2/9.3** (delivery) → `role_for_branch` exact-match; `TelegramClient` 4096 constant + plain text + `raise_for_status`; `telegram_channels` JSON `dict[int,str]`; `DeliveryPlan.language` lowercase `"ru"`. Watch: `DeliveryService` has no per-push trigger — first caller is the daily report (Phase 10).
- **10.1.1/10.1.2/10.2/10.3** (reporting) → biggest fix: `lang` was absent from `ReportSection.render` in 10.1.1 but assumed by 10.1.2/10.3 — threaded `lang="ru"` through `render`/`build`/`report_notes`. Also: join separator `"\n\n"`; `report_schedules` JSON `{name, window:<days int>, sections}`; `RemainingSection` reads at `after` (not literal HEAD); `PerBranchSection` derives the time boundary from `before`/`after` commit dates (a single canonical-ref SHA range names no other branch's commits). Watch: `report_notes` reuses 8.2.1's exact dispatch.
- **Docs restructure** → `docs/spec/`→`docs/behavior/` (+ `-overview`); all links swept. Watch: handoffs intentionally NOT updated (frozen).
- **Concepts** → `product-scope.md` (tenant→product→repo, membership≠dependency, per-product channel, activation gate) and `coordination-root-format.md` (the published `## Coordination` format). Watch: product-scope's "Seeded" path == coordination-root seeding == 6.2; membership (repo→product) is a *different* relation from the graph's dependency edge.
