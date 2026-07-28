# Handoff — Deferred-observations resolution (73 unpinned entries blocking the prune)

## 1. Frame

Herald (repo-stats-herald) — `/roadmap-prune` was invoked on `.ai-factory/ROADMAP.md` and stopped dead at its Step-0 deferred-observations gate: **73 entries across `plan-reviews/` and `reviews/` carry no status marker, and no resolution session has ever run in this repo**; the originating session's context isn't available here — trust these files, not memory.

## 2. Read-first map

The next step is a **dedicated resolution session** that disposes of the 73 entries and pins each one. The rehydration set is scoped to that: the marker grammar, the inventory, and the reason the work is urgent.

### Must-read now (minimal rehydration set)

- **§10 and §11 of THIS handoff** — §11 *is* the work-list (all 73 entries with their `file:line` anchors); §10 is the grammar and dedup rule that must be applied identically to every one of them. ← lead here
- `~/.claude/skills/orchestrator-artifacts/SKILL.md` **§5–§6** — the normative definition of the `## Deferred observations` section format and the status-marker grammar. Do not re-derive the grammar from this handoff; cite the engine. §11's inventory is a pointer table, the engine is the contract.
- `~/.claude/skills/roadmap-prune/SKILL.md` **Step 0** — the gate that blocked, and its exact resolution protocol (handoff → dedicated resolution session → re-run). Read it to understand what "the gate passing is the resolution's proof, never manufactured" forbids.
- `.ai-factory/ROADMAP.md` — needed to answer the single hardest question per entry: *is the task this observation should route into still open?* `[routed → <path>]` may only name an **open** task's spec. Everything through Phase 12.2 is `[x]`; the open `[ ]` seam is where routes are legal.
- The actual review files named in §11 — **the full reviewer prose is not reproduced in this handoff.** Nothing was swept, so every entry is still readable verbatim at its `<file>:<line>` anchor. Open the anchor before deciding an entry's disposition; the gists in §11 are navigation, not evidence.

### Read on demand

- `.ai-factory/specs/` — 52 task specs. The `Spec:` tag on each contract line resolves an entry's `Affects:` target to an editable surface. Relevant only for entries you route.
- `.ai-factory/ARCHITECTURE.md` — its `## Features` header carries no `roadmap-prune vN` marker, so the eventual prune run will trigger the 4.2a legacy self-heal pre-pass (drop-history rebuilt from git, header stamped `v2`). Not needed for the resolution work itself.
- `docs/behavior/` — the governing behavioral spec. Consult only when an entry's disposition turns on intended behavior rather than code (e.g. the Telegram 4096-character-boundary entry, #45/#73, is explicitly framed as a governing-spec decision).

## 3. Current state

**Done:**
- Full Step-0 gate scan of `.ai-factory/plan-reviews/` and `.ai-factory/reviews/` at any depth: 61 unpinned entries under `plan-reviews/`, 12 under `reviews/`, **73 total**.
- Repo-wide grep for the entire marker vocabulary — `[fixed]`, `[dismissed]`, `[routed → <path>]`, plus the retired legacy set `[promoted → <path>]`, `[audit-corroborated]`, `[audit-dismissed]`, `[unrouted-reported]` — returned **zero hits**. Pin count is genuinely 0, not a scan artifact.
- The complete inventory enumerated with `file:line`, `Affects:` target, and gist (§11 below).

**In-flight:**
- The prune itself is **parked, not failed**. It made no edits: no artifact sweep, no `ARCHITECTURE.md` write, no `ROADMAP.md` change, no spec deletion, no partial prune.
- The resolution session has not started. That is the next step.

**Uncommitted working-tree state:**
- None at gate time — the tree was clean at `2dafad8`. This handoff file is the only new artifact.

## 4. Next step

Open a **dedicated resolution session** and work the §11 inventory top to bottom. For each entry: open its `file:line` anchor, read the reviewer's actual prose, then dispose of it one of three ways — fix the gap directly in this session (`[fixed]`), route it into an **open** task's spec (`[routed → <path>]`), or evaluate it as moot/stale/already-handled (`[dismissed]`). Append the marker to the entry line per §10; never rewrite the entry text or its `Affects:` field. Apply the dedup rule as you go — one decision pins every occurrence of that observation across the task's review files. When every entry is pinned, re-run `/roadmap-prune`. The user (max) approves dispositions; the agent reads, decides-with-approval, and writes the markers.

## 5. Working discipline

- **Chat plans; the orchestrator implements** (global CLAUDE.md). A `[fixed]` disposition that touches `src/`/`tests/` is *not* free — in a planning session the honest disposition is usually `[routed → <spec>]`, deferring the edit to the orchestrator. Reserve `[fixed]` for gaps genuinely closable in the artifact layer, or run the resolution in an implementation-capable session and say so.
- **Never commit without explicit permission.** Uncommitted changes are assumed intentional.
- **The gate is not negotiable.** Do not pin an entry to unblock the prune. A marker asserts a decision was made; manufacturing one to pass the gate is the single failure mode this whole protocol exists to prevent.
- **Ask before routing.** Routing writes a clause into another task's spec — confirm the target and the wording before editing a sibling artifact.
- Language: artifacts in **English**; chat replies to this user in **Russian**.

## 6. Error log

- **Nearly reported the gist table as the deliverable.** The initial gate output truncated every entry to 190 characters. That is adequate for navigation and inadequate for disposition — a truncated observation cannot be judged. Correction: the handoff carries `file:line` anchors and states explicitly that the full prose stays at the anchor, because the sweep has not run and the review files are all still on disk. If a future run *does* sweep first, the prose is gone and the entries become undecidable — capture before sweeping, never after.
- **The pin-detection heuristic needed a second check.** The first pass matched entry text ending in `\[[^\]]+\]` and returned 0 pinned out of 73 — a suspiciously round result that could equally mean "the regex is wrong." Correction: a direct grep for the literal marker vocabulary confirmed zero markers exist anywhere in either directory. Never accept a zero from a single derived heuristic; corroborate with a literal search.

## 7. Orientation

- **`plan-reviews/` entries vs. `reviews/` entries are shaped differently.** The 61 `plan-reviews/` entries follow the engine format: `- Affects: <target> — <observation>`. The 12 `reviews/` entries (§11, entries 62–73) are free-form bold-lead bullets with **no `Affects:` field at all**. They are still gate entries and still require markers. Do not skip them because they don't match the canonical shape.
- **Non-standard section headers are still matched.** Several files carry suffixed headers — `### Deferred observations (out of scope for 4.2.2 — noted for later hardening)`, `## Deferred observations (non-blocking)`, `## Deferred observations (not defects in this task's scope)` — and two use `###` instead of `##`. The gate matches by prefix, so all of them count. A parenthetical "non-blocking" in the header does **not** mean pre-dismissed; it means the reviewer passed the task, not that the observation is disposed of.
- **"Deferred observation" ≠ "finding".** A review with only deferred observations still passes. These are non-findings by construction — the resolution session decides their fate, it is not re-reviewing failed work.
- **The prune gate (Step 0) vs. the plan-layer citation scan (Step 7.5).** Both scan and report; only Step 0 blocks. Step 7.5 never ran this session — the run stopped before it.
- **Deferred observations vs. plan-review *findings*.** Findings were fixed during the orchestrator loop and are already resolved in the round-N files. Only the `## Deferred observations` sections are in scope here.

## 8. Domain model spine

- **Pinned = the entry line carries ≥1 bracketed status marker.** Not "was read", not "was discussed", not "the reviewer said non-blocking". Don't re-litigate — `orchestrator-artifacts` §6.
- **The gate is repo-wide by design.** Prune is an integration-branch act, so any unpinned observation blocks it regardless of which task or author produced it. Don't re-litigate the scope — `roadmap-prune` Step 0.2.
- **The resolution session is a separate session, deliberately.** The protocol routes through a handoff precisely so the deciding agent isn't the one that wants the prune to pass. Don't collapse the two.
- **This repo is solo** — no `.ai-factory/roadmaps/`, so the eventual prune takes the default-pair branch and `rm -rf`s the flat `plans/`, `plan-reviews/`, `reviews/`. That is exactly why resolution must precede the prune: **the sweep destroys the files these observations live in.** There is no recovering an unresolved observation afterward except from git.

## 9. Hard rules

- Never commit without explicit permission; the prune's own commit happens **only on request**, exactly one commit, message exactly `Roadmap prune`, no body, no prefix, no co-author line.
- The prune's sweep uses `rm` / `find -delete` — **never `git rm`**. Staging happens once, at commit time, via `git add -A`.
- `.ai-factory/handoffs/` is **never swept** by the prune. This file survives the eventual prune run.
- `[routed → <path>]` must resolve to an **open** task's spec — never a completed or frozen one. A route into a `[x]` task's spec is a dead letter.
- Markers are **append-only**. Entry text and `Affects:` are never rewritten; markers only accumulate.
- Artifacts in English regardless of conversation language.

## 10. Cross-cutting contracts / invariants checklist

Apply these identically to all 73 entries — this is the section the resolution session works from.

- **Marker placement** — a space-separated bracketed suffix appended at the **end of the entry line**. Multi-line entries take the marker at the end of the entry's final line.
- **The three live markers** — `[fixed]` (gap closed directly in the resolution session), `[routed → <path>]` (routed into an open task's spec; `<path>` must resolve to an editable surface), `[dismissed]` (evaluated and found moot, stale, or already handled).
- **The retired legacy markers** — `[promoted → <path>]`, `[audit-corroborated]`, `[audit-dismissed]`, `[unrouted-reported]`. Never write these; they still count as pinned where they appear in old repos (they appear nowhere here).
- **The dedup rule** — whoever pins an entry pins **every occurrence across that task's review files**, deduped by `Affects:` target + gist. This is the highest-leverage rule in this handoff: many of the 73 are the same observation restated across review rounds. Worked examples:
  - the double-mirror-refresh note → `25-…-plan-review-1:48`, `-2:42`, `-3:50`, and again `reviews/25-…-review-2:62` (4 occurrences, 1 decision);
  - `neighbors` without `DISTINCT` → `33-…-plan-review-1:32`, `-2:35`, `reviews/33-…-review-1:25` (3 occurrences, 1 decision);
  - the Telegram token-in-URL leak → `43-…-plan-review-1:36`, `reviews/43-…-review-1:27` (2 occurrences, 1 decision);
  - the cross-path roadmap move → `23-…-plan-review-1:27`/`-2:32`, `24-…-plan-review-1:39`/`-2:37`, `reviews/24-…-review-1:44` — note this one spans **two tasks**, so the dedup rule's "that task's review files" scoping means it is formally two decisions even though the substance is one.
  - **Expected collapse: 73 occurrences → roughly 45–50 distinct decisions.**
- **The reviewer never writes markers**; only the resolution session does. If an entry looks pre-marked, verify it isn't reviewer prose that happens to end in a bracket.
- **A dismissal is a decision, not a shortcut.** `[dismissed]` asserts the entry was evaluated and found moot — it is a legitimate and common outcome here (many entries are explicitly "no action needed, noted only"), but it must be reached by reading the anchor, not by pattern-matching the gist.

## 11. Per-unit map with watch-points — the complete 73-entry inventory

Grouped by review file. Format: `#N` · `<file>:<line>` · `Affects:` target · gist. **Full reviewer prose lives at the anchor** — nothing was swept, every file is on disk.

### `plan-reviews/` — 61 entries

**`08-eval-harness-case-type-registry-plan-review-1.md`**
1. `:36` — *later prose-producer phases (5.2.2, 7.1.2, 8.1, 10.1.2, 11.2.2)* — `CaseHandler` ABC lands in `scripts/eval.py`, so future subclasses must stay on the eval side; a `src/` feature subclassing a composition-root ABC inverts the dependency rule. **Watch:** this one constrains five later phases, all now `[x]` — check whether the inversion actually happened before dismissing.

**`09-2-1-1-push-event-models-webhook-contract-red-tests-plan-review-{1,2}.md`**
2. `-1:41` — *task 2.1.2 (`specs/01-signed-webhook-receipt.md`)* — the valid-signature red test asserts fields from the **HTTP response body**, binding 2.1.2 to echo the parsed `PushEvent`; a production receiver would return a minimal `200`.
3. `-1:42` — *local-dev tooling (`Makefile` `dev`/`eval`, `scripts/*.py`)* — required `github_webhook_secret` with no default breaks any run that instantiates `Settings`.
4. `-2:31` — *task 2.1.2* — #2 restated. **Dedup with #2.**

**`12-3-1-1-mirror-isolation-auth-contract-red-scenarios-plan-review-{1,2}.md`**
5. `-1:36` — *3.1.2 / `specs/04-repo-mirror.md`* — the plan pins the mint step to the method name `_mint_token` (a test patches that exact attribute) but the spec never mentions it.
6. `-2:31` — *3.1.2 / `specs/04-repo-mirror.md`* — #5 restated. **Dedup with #5.**

**`13-3-1-2-repo-mirror-impl-plan-review-{1,2}.md`**
7. `-1:33` — *task 3.4.2 / 3.6 (the consumer)* — "the composition root asserts the App/mirror settings are set" but only a module docstring is written; no actual assertion exists.
8. `-2:25` — *task 3.4.2 / 3.6* — #7 restated with the settings named (`github_app_id`/`github_app_private_key_path`/`mirror_root`). **Dedup with #7.**
9. `-2:26` — *task 3.4.2 / 3.6 (prod http path only)* — the installation token passed via `git -c http.extraheader=…` lands in process argv, briefly visible to other host processes. **Watch:** security-shaped; pairs with #63 (token TTL) and #44/#72 (token in URL) as the credential-handling cluster.

**`14-3-2-ollama-embeddings-boundary-plan-review-{1,2}.md`**
10. `-1:29` — *task 3.4 / spec verification* — no automated verification; the roadmap's "`embed([...])` → fixed-dim vectors through the tunnel" stays a manual call.
11. `-2:30` — *task 3.3 (`vector(<dim>)` column) / task 3.4* — the embed dimension is unverified before the `vector(<dim>)` column pins it. **Dedup candidate with #10** — same `Testing: no` gap, different consequence named.

**`15-3-3-1-knowledgestore-contract-schema-red-tests-plan-review-1.md`**
12. `:28` — *dev-machine provisioning* — the `pg_pool` fixture calls `create_pool(dsn)` **before** applying `schema.sql`; `asyncpg` opens `min_size` connections eagerly, so each connection's `init` runs against a schema-less DB.

**`16-3-3-2-pgvectorstore-impl-plan-review-{1,2}.md`**
13. `-1:49` — *future composition roots / `tests/knowledge/conftest.py`* — the derived `postgres_dsn` string-interpolates user/password into a URL **without percent-encoding**.
14. `-2:38` — same. **Dedup with #13.**

**`18-3-4-2-artifact-indexer-impl-plan-review-1.md`**
15. `:31` — *indexer verification (integration / 3.6 wiring)* — `ArtifactIndexer` ships under `Testing: no`; the greened red tests cover only the pure `selects`/`chunk_markdown` surfaces, never the indexer's own embed↔chunk orchestration.

**`19-3-5-installation-repositories-tracking-plan-review-{1,2}.md`**
16. `-1:35` — *infra / future Phase-3 wiring* — `src/core/db.py::create_pool` unconditionally registers a `vector` type codec on every connection, so any pool fails to start without the pgvector extension present.
17. `-2:34` — same, framed at the lifespan / OID-resolution level. **Dedup with #16; also dedup with #35** (same codec constraint, different task).

**`20-3-6-populate-and-keep-fresh-plan-review-1.md`**
18. `:37` — *task 3.4 boundary (`src/knowledge/source_strategy.py` / `indexer.py`)* — `AiFactorySourceStrategy.selects` returns `True` for **anything** under `docs/`, while `ArtifactIndexer.index` then `read_text`s it — binaries blow up.
19. `:39` — *a later phase / the 3.5→3.6 linkage* — the 3.5 contract line says `served_repos` is "consumed by 3.6's on-install backfill," but 3.6 ships only a manual `scripts/backfill.py` entrypoint and never consumes it. **Watch:** this is a contract-line-vs-code divergence, not a nicety.
20. `:41` — *a future prod/webhook hardening phase* — the composition root gates the whole sync chain on **all** of `github_app_id`, `github_app_private_key_path`, `mirror_root`, `github_org_logins`; partial config silently disables sync.
21. `:43` — *a future throughput/hardening phase* — `on_push` runs as an async `BackgroundTask` but `RepoMirror`'s git calls are blocking `subprocess.run` on the event loop.

**`23-4-2-1-linked-change-contract-resolve-tests-red-plan-review-{1,2}.md`** *(note: `-1` uses a `###` header)*
22. `-1:27` — *4.2.2 (`specs/11-linked-change-resolver.md`)* — the `SourceStrategy` ABC exposes only `selects(path) -> bool`; it cannot return or enumerate a roadmap path, so specs 11/45's "roadmap path from the source strategy, not hardcoded" is unsatisfiable as written.
23. `-2:32` — same. **Dedup with #22.**
24. `-2:33` — *4.2.2 and later real-roadmap consumers* — done-marker keying is scoped to lines with a leading `N.N.N`; a line lacking one is declared out of scope for the milestone. **Watch:** interacts with #64 — the implementation used `search`, not a leading-anchor match.

**`24-4-2-2-linked-change-resolver-impl-plan-review-{1,2}.md`**
25. `-1:39` — *future consumers / `specs/11-linked-change-resolver.md`* — "pick the first candidate present at either ref" reads `before` and `after` from a **single** chosen path; a roadmap moved across paths within one range misreads.
26. `-2:37` — same. **Dedup with #25 — and with #65 in `reviews/`.**

**`25-4-3-episodic-writer-on-push-plan-review-{1,2,3}.md`**
27. `-1:48` — *Phase 4 write-path efficiency* — both `KnowledgeSync.on_push` and `EpisodicWriter.write` independently call `mirror.ensure` (a `git fetch --prune`) and open a worktree at `push.after` on every served push.
28. `-2:42` — same. **Dedup with #27.**
29. `-3:50` — same. **Dedup with #27 — and with #67 in `reviews/`. Four occurrences, one decision.**

**`26-4-4-historical-backfill-plan-review-{1,2,3}.md`**
30. `-1:40` — *Task 1 (`src/commits/collector.py`)* — existing collector methods pass `--end-of-options` before user-supplied refs; the new call omits the guard, so a ref shaped like an option is interpreted as one.
31. `-1:41` — *Task 4 (`src/episodic/backfill.py`)* — the "skip a step with no tasks and no commits" guard is unreachable for a valid first-parent step (`git log before..after` always yields at least `after`); harmless dead code.
32. `-2:29` — *4.4 (performance, within-design)* — one embed HTTP call per historical step, plus a full roadmap re-read at both refs and a `--numstat --shortstat` `git log` per step.
33. `-3:33` — same, widened to *4.4 / 5.4*. **Dedup with #32.**

**`28-5-2-1-code-distiller-contract-grouping-tests-red-plan-review-1.md`**
34. `:37` — *5.2.2 (`specs/33-code-to-feature-distillation.md`)* — `compose` is pinned to join per-unit strings with a bare `"\n\n"`; adequate for the red task's determinism assertion, questionable once 5.2.2 greens it.

**`32-6-1-1-project-graph-contract-schema-red-tests-plan-review-1.md`**
35. `:30` — *machine/environment setup* — `create_pool` registers the `vector` codec on every connection, so the graph schema requires the extension to pre-exist even though the graph itself doesn't use vectors. **Dedup candidate with #16/#17.**

**`33-6-1-2-pgprojectgraph-impl-plan-review-{1,2}.md`**
36. `-1:32` — *Phase 6 cross-project narration (future consumer)* — `neighbors(repo)` has no `DISTINCT`, so two edges of different `kind` between the same pair return a duplicate `to_repo`.
37. `-2:35` — same. **Dedup with #36 — and with #69 in `reviews/`.**

**`35-6-2-coordination-root-seeding-plan-review-{1,2}.md`**
38. `-1:46` — *unknown (future consumer)* — the seeder opens a **second** worktree via `mirror.tree(...)` after `backfill`/`on_push` already opened and released one for the same ref; reclamation is deferred to the next `ensure`.
39. `-2:41` — same, framed as the RepoMirror deferred-reclamation design. **Dedup with #38 — and related to #62, the restart-survival leak.**

**`37-7-1-2-reasoner-core-impl-plan-review-{1,2}.md`**
40. `-1:33` — *task 7.2 (cross-project reach)* — `GatheredContext` is introduced as the shared retrieval shape 7.2 and 8.1 extend, but its placement blocks that extension.
41. `-2:80` — same, widened to *7.2 / 8.1*, arguing the internal-to-`reasoner.py` placement is correct **for 7.1.2** but not beyond. **Dedup with #40.**

**`39-8-1-reasoner-narrate-plan-review-{1,2}.md`**
42. `-1:34` — *Phase 3 / user-authored eval data (`evals/cases.yaml`, `evals/reference/`)* — the `narrate` handler is registered but no `narrate` case and no reference note exist, so harness verification is latent until a user authors them. **Watch:** references are user-authored and never fabricated (CLAUDE.md) — this can only be closed by the user.
43. `-2:33` — same. **Dedup with #42 — and with #71 in `reviews/`.**

**`43-9-2-telegram-client-plan-review-{1,2}.md`**
44. `-1:36` — *task 15.3 / any future caller that logs `TelegramClient` errors* — the Bot API embeds the secret token in the request URL; `raise_for_status()` raises an error whose string form includes that URL, so the token leaks into logs.
45. `-2:34` — *Phase 9 / `specs/15-telegram-client.md`* — the spec and roadmap mandate splitting on the Python "character boundary," but Telegram's 4096 limit counts **UTF-16 code units**. **Watch:** explicitly a governing-spec decision — the fix may belong in `docs/behavior/delivery.md`, not the code.

**`47-10-2-report-schedules-delivery-plan-review-{1,2,3}.md`**
46. `-1:64` — *repo tooling (`deploy/` does not yet exist)* — a task writes `deploy/report-crons.crontab` into a directory not present in the repo; the write creates it. Explicitly "no action needed, noted only."
47. `-2:52` — *task 10.3 (report localization)* — delivery is hard-coded to `plan.language` (default `"ru"`), with 10.3 threading non-RU later.
48. `-3:33` — same. **Dedup with #47.**

**`48-10-3-report-localization-plan-review-{1,2}.md`**
49. `-1:36` — *Phase 11 (`11.2.2`/`11.3`, specs `20-release-note.md`, `21-github-release.md`)* — widening `report_notes` to `dict[str, str | None]` ripples to consumers that index the result directly (`notes[plan.language]`, `notes[plan.github_release_language]`) and assume non-`None`. **Watch:** Phase 11 is now `[x]` — verify whether the ripple was actually absorbed.
50. `-1:37` — *Verification / eval harness* — with `PivotLocalizer(pivot="en")` as the shipping default, a `"ru"` channel's report is generated natively in English and machine-translated, not built natively in Russian.
51. `-2:38` — #49 restated (release path). **Dedup with #49.**
52. `-2:39` — #50 restated. **Dedup with #50.**

**`49-11-1-versioning-back-merge-skip-plan-review-1.md`**
53. `:29` — *task 11.3 (the push-event → `Versioner.next` wiring)* — the STAGING back-merge guard treats an empty `new_commits(...)` result **including a non-zero `git` exit** as a back-merge → `None`. **Watch:** an error is silently indistinguishable from a legitimate skip.

**`50-11-2-1-sincedeploywindow-red-tests-plan-review-{1,2}.md`**
54. `-1:100` — *11.2.2 (release-note impl)* — `after = "HEAD"` stays a literal ref rather than a resolved SHA (correct per spec), so the consuming pipeline must treat it as a live ref.
55. `-2:108` — same. **Dedup with #54.**

**`51-11-2-2-release-note-as-a-report-impl-plan-review-1.md`**
56. `:28` — *task 11.2.2 (implementation reasoning)* — the plan justifies `None`-defaulted keyword collaborators by claiming the window/section "fail lazily at `resolve`/`render`, the same lazy pattern `TimeWindow` uses"; the reviewer judges the symmetry unsound.

**`52-11-3-github-release-version-header-plan-review-1.md`**
57. `:44` — *Phase 12.1 (`specs/22-changelog-protocol-client.md`)* — the plan pins `changelog_client.config(base_url)` as returning an object exposing `.languages: list[str]` while 12.1's frozen contract states `GET config → {languages:[string]}`. **Watch:** a frozen contract vs. an assumed shape — 12.1 is now `[x]`, so check which won.

**`53-12-1-changelog-protocol-client-frozen-contract-plan-review-{1,2}.md`**
58. `-1:34` — *operator configuration / `.env.example`* — the new `REPO_APPS` env setting gets no `.env.example` entry (`Docs: no`), unlike its sibling JSON-dict settings (`CANONICAL_REFS`, `GITHUB_ORG_LOGINS`, `PROJECT_EDGES`).
59. `-2:31` — same, noting `.env.example` is outside the task's declared file boundary. **Dedup with #58.**

**`54-12-2-changelog-channel-wiring-plan-review-{1,2}.md`**
60. `-1:37` — *Phase 11/12 (`src/ingestion/router.py::_deliver_release`)* — the release fan-out is a growing module-level orchestration inside the ingestion router, in tension with ARCHITECTURE.md's "routers are thin, services own business logic."
61. `-2:40` — same. **Dedup with #60. Watch:** this is the only entry that names an ARCHITECTURE.md violation directly.

### `reviews/` — 12 entries (free-form bullets, **no `Affects:` field**)

**`13-3-1-2-repo-mirror-impl-review-1.md`** *(`###` header)*
62. `:37` — **worktree reclamation does not survive a process restart** — `tree()`'s `finally` records finished worktrees in an in-memory structure; across restarts this is an unbounded disk leak. Framed as a consumer/composition-root task. **Related to #38/#39.**
63. `:39` — **`mint_token` caches a fixed TTL, not the server's `expires_at`** — `_VALID_FOR_SECONDS = 3600 - 300` (`app_auth.py:10`) hard-codes GitHub's current 1h lifetime with a 5-min margin.

**`24-4-2-2-linked-change-resolver-impl-review-1.md`** *(header suffixed "(out of scope for 4.2.2 — noted for later hardening)")*
64. `:43` — **first-dotted-number heuristic vs. "leading identifier" wording** — `_TASK_ID_RE.search(line)` takes the *first* `\d+(?:\.\d+)+` anywhere on a done line, not a leading-anchored one. **Pairs with #24.**
65. `:44` — **cross-path roadmap move within one range** — explicitly carried forward from plan-review-1. **Dedup with #25/#26.**

**`25-4-3-episodic-writer-on-push-review-2.md`** *(header suffixed "(non-blocking)")*
66. `:61` — **empty-`content` edge** — optionally skip the append when `content == ""` if empty-range/rewind pushes are expected; the failure is now logged, not fatal.
67. `:62` — **double mirror refresh**, carried from review 1 and the plan. **Dedup with #27/#28/#29.**

**`33-6-1-2-pgprojectgraph-impl-review-1.md`** *(header suffixed "(not defects in this task's scope)")*
68. `:24` — **dropped config edges are not pruned at startup** — the startup loop upserts the currently-declared `PROJECT_EDGES` but never removes a `config` row for an edge the operator has since deleted.
69. `:25` — **`neighbors` can return a duplicate `to_repo`** — matches the pinned 6.1.1 contract, so this is a contract question, not a bug. **Dedup with #36/#37.**

**`39-8-1-reasoner-narrate-review-1.md`** *(header suffixed "(non-blocking, out of scope for this task)")*
70. `:25` — **test fixture realism vs. real `completed_tasks`** — `test_completed_tasks_are_included_in_the_retrieval_query` uses `"8.1 — Reasoner narrate"` as a completed task, a shape `LinkedChangeResolver` would not actually produce.
71. `:26` — **eval linkage latent** — no `narrate` case in `evals/cases.yaml`, no reference note. **Dedup with #42/#43.**

**`43-9-2-telegram-client-review-1.md`**
72. `:27` — **token-in-URL can leak through error logging** — explicitly marked out of scope, future consumer boundary. **Dedup with #44.**
73. `:28` — **4096 limit is UTF-16 code units, chunking uses Python `len`** — explicitly marked a governing-spec decision, out of scope. **Dedup with #45.**
