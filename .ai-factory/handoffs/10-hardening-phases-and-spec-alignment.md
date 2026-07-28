# Handoff — Hardening phases, pinned observations, and spec alignment

## 1. Frame

Herald (repo-stats-herald) — all 76 deferred observations are pinned, so `/roadmap-prune`'s Step-0 gate is passable on its own evidence; five new phases (18–22, 17 open tasks, specs `53`–`69`) sit above `---STOP---` awaiting the orchestrator, and the governing docs have been corrected against what actually ships — the originating session's context isn't available here; trust these files, not memory.

## 2. Read-first map

Two work-units live in this handoff and they resume at different moments. **Unit A** is the implementation queue — 17 open tasks the orchestrator works through. **Unit B** is the live test run against a real repository, which is what the user wants once the queue drains. They cross-link at exactly one place: 21.4 must land before any harness run, and Phase 13 (production deployment) is undecomposed, which is what a live run will collide with first.

### Unit A — the implementation queue

#### Must-read now (minimal rehydration set)

- `.ai-factory/ROADMAP.md` — the whole open seam. Everything above `---STOP---` is orchestrator-ready; the `[ ]` lines in Phases 18–22 are the queue, in the order the file lists them. Phase 22 sits **first**, before Phase 18, deliberately. ← lead here
- `.ai-factory/specs/53` … `69` — one spec per open task, resolved through each contract line's `Spec:` tag. The contract line is the header; the spec holds current state, the change, files, guards, and verification. Never implement from the contract line alone.
- `CLAUDE.md` — how to work in this code: the composition-root rule, constructor DI, the feature-vs-infra boundary, the eval harness, logging. Its `## Status`, `## Stack`, and module table were corrected this session and now describe what ships (Phases 1–12), so it is trustworthy again.
- `docs/behavior/delivery.md` — the governing spec three tasks build directly against: the staging release-candidate rule including a newly created branch's first push (18.1), back-merge detection and what happens when the reading fails (18.2.x), and the Telegram message-boundary counting rule (19.4).

#### Read on demand

- `.ai-factory/ARCHITECTURE.md` — module boundaries, the dependency rules, and the named anti-pattern ("logic in entry points") that Phase 20.1 exists to undo.
- `docs/behavior/understanding.md` — the two memories, retrieval, and the initial-index pass that 18.3 wires.
- `docs/concepts/` — six forward-looking designs. Only `source-strategy-profiles.md` and `code-derived-understanding.md` describe shipped behavior; the other four are genuinely unbuilt and say so.
- `~/.claude/skills/orchestrator-artifacts/SKILL.md` §5–§6 — the status-marker grammar, if any question about the pinned observations arises.

### Unit B — the live run on a real repository

#### Must-read now (minimal rehydration set)

- `docs/behavior/ingestion.md` — the GitHub App webhook, the installation as trust boundary, and the serve-allowlist. A live run stands or falls on the allowlist and the App installation being right. ← lead here
- `docs/behavior/configuration.md` — the resolver seam and every setting a run needs.
- `.env.example` and `src/core/config.py` — the actual settings surface. `Settings` gates the composition root: `src/main.py` assembles the mirror/sync/delivery chain only when `github_app_id`, `github_app_private_key_path`, `mirror_root`, and `github_org_logins` are **all** present, and logs a warning instead when they are not. A partially configured environment starts and does nothing.
- `.ai-factory/ROADMAP.md` Phase 13 — production deployment, still prose with no tasks. A live run on a server is blocked on it; a live run against a real repo from a dev machine over the SSH tunnel is not.

#### Read on demand

- `CLAUDE.md` "First-time setup — database" — pgvector must exist before any pool opens; `create_pool` registers the `vector` codec on every connection unconditionally.
- `evals/cases.yaml` and `evals/reference/` — six cases, six references. Quality is judged by a person reading an output against its reference; the harness does not diff.

## 3. Current state

**Done:**
- **All 76 deferred observations pinned** across 59 files under `.ai-factory/plan-reviews/` and `.ai-factory/reviews/` — 14 routed into open task specs, 62 dismissed, zero `[fixed]` (nothing under `src/` changed while resolving, so `[fixed]` would have been a lie). Append-only proved mechanically: for all 76 changed lines the pre-edit line is a byte-exact prefix of the post-edit line. Commit `fe15c34`.
- **Phases 18–22 outlined and decomposed** — 17 open tasks, specs `53`–`69`. Phase 18 silent release loss and unwired promises; 19 boundary representation mismatches; 20 thinning the ingestion router; 21 ground truth for the eval harness; 22 removing a foreign product's name from live docs.
- **Skeleton/TDD/concurrency lens run over Phases 18–21** — two splits earned it: `18.2` → `18.2.1` (failure-signal contract, red tests) + `18.2.2`, and `20.2` → `20.2.1` (concurrency contract, red scenarios) + `20.2.2`. Twelve tasks passed through untouched.
- **Six eval reference notes authored and approved** by the user — `herald-recent`, `herald-recent-en`, `herald-localize`, `herald-self-query`, `mind-features`, `herald-narrate`. Commits `f88d3da`, `0cef3a6`. Tasks 21.2 and 21.5 are `[x]`.
- **The distill case retargeted** from a foreign product to `mind_api`; the case is `mind-features`, root `/Users/max/projects/mind/mind_api`.
- **Docs corrected against shipped code** — eight files. Three silences in the governing spec closed (first push to a new `staging` branch, back-merge detection failure, Telegram message boundary), and `CLAUDE.md`/`README.md` no longer describe a Phase-1 project. Task 19.3 is `[x]` because its whole deliverable was that doc rule. Commit `7699952`.

**In-flight:**
- **Nothing is implemented.** Every one of the 17 open tasks is planning only; no file under `src/` or `tests/` changed this session.
- **The prune has not been re-run.** Its gate now passes, but the sweep is destructive and was deliberately not triggered.

**Uncommitted working-tree state:**
- `M .ai-factory/ROADMAP.md` and `M .ai-factory/specs/60-release-delivery-extraction.md` — the flipped guard on 20.1 (read the changelog base URL as a plain attribute, not through an unreachable defensive lookup).
- `D .ai-factory/notes/09-architect-buffer.md` — the architect's private buffer, emptied and deleted; every item in it was either done or already recorded in the roadmap, specs, or docs.

## 4. Next step

The orchestrator implements the open tasks in the order `.ai-factory/ROADMAP.md` lists them, starting with 22.1 and ending with 21.x. Each task is implemented from its spec, not from its contract line. The user reviews and rules every fork; the agent decides nothing structural alone. Once the queue drains, the user wants a live test run against a real repository — at that point re-read Unit B's map above, and expect Phase 13 to be the first thing missing.

## 5. Working discipline

- **The user rules every fork.** Surface a genuine choice crisply and let them decide; do not bury it in a task. They corrected this session explicitly: *"я сам скажу, когда планирование закрыто и когда проставить пины"* — do not declare a phase of work finished or push toward the next one.
- **Chat plans; the orchestrator implements.** Do not start editing `src/` on your own initiative.
- **Docs are editable and are the governing spec.** The user ruled: *"Это тех задание, на котором строится код. И тех задание обязано отражать желаемое положение вещей."* A task must be able to lean on a correct spec, because the orchestrator cannot ask a question — where the spec is wrong or silent it invents.
- **Verify by fact, never by report.** A subagent's report is a hypothesis. Run the greps and reads yourself against the real files; several of this session's most consequential corrections came from doing exactly that.
- **Never commit without explicit permission.** The user asks for a commit by name.
- Artifacts in **English**; chat replies to this user in **Russian**.

## 6. Error log

- **Three self-check errors in apply work-orders, all the same root cause.** (1) Stated "exactly five paths" while listing six. (2) Required `grep -c "not built" README.md` to be `0` while the same order pinned replacement text ending "…are specified and not built yet". (3) Stated "exactly two paths" while editing a third file personally in the same turn. **Correction that worked:** every work-order now carries *"where a count disagrees with what I state, report the real number and stop rather than adjusting the file to match."* Without it a receiver either buries the discrepancy or edits the file to satisfy a wrong number. Never state an expected count without reconciling it against what the same order pins and what you are doing yourself in the same turn.
- **A U+2026 ellipsis typo shipped into a pinned contract line** — `git rev-list 000…..after` instead of `git rev-list 000..after`, inserted verbatim because the order said verbatim. Fixed in a follow-up round. Proofread pinned literals character by character; a receiver told to copy exactly will copy your typo exactly.
- **Two specs claimed the same docstring rewrite, and one was self-contradictory** — spec `65` simultaneously required `new_commits`'s body unchanged, the docstring stating the new contract, and the docstring never describing behavior the code lacks. Fixed: the impl task owns the rewrite, at the moment the body matches.
- **The prior editor's stale claims were taken at face value once.** Three of its eight "live gaps" were already closed in code: the installation token now goes through `GIT_CONFIG_*` env vars rather than argv (`src/github/mirror.py:188-203`), `sweep_worktrees()` is wired at four composition roots, and `indexer.py` wraps `read_text` in `except UnicodeDecodeError`. It had reused its own earlier conclusions without re-reading the code. Re-verify every claim that would create work.
- **My own hazard claim was refuted by the schema.** I argued 18.3 needed a concurrency contract because overlapping backfills would duplicate chunks; `chunks` carries `PRIMARY KEY (repo, path, chunk_index)` and `upsert` is DELETE-then-INSERT per `(repo, path)`, so duplication is impossible. The split was dropped and a narrower guard kept instead.
- **Over-corrected the user's vocabulary.** They rejected «выкатка»; I removed «деплой» along with it. «Деплой» is the right word and pairs with `deployment` in the English references and `SinceDeployWindow` in the code. Restored.
- **"Replace the whole body" cost a navigation edge** — README's `See [the specification](docs/behavior-overview.md)` line was removed because the instruction was read literally, correctly. Restored in a follow-up.

## 7. Orientation

- **A completed task's spec is a dead letter for routing.** `[routed → <path>]` may only name an **open** task's spec. Specs `63` (21.2) and `69` (21.5) went `[x]` this session and must never appear in a route.
- **`narrate` takes a singular `lang`; `localize` takes a plural `langs`.** `NarrateCaseHandler.run` reads `inputs.get("lang", "ru")`. Copying the neighbouring localize case's key shape is the easy mistake.
- **A Python `str` holds no surrogate pairs.** `len('😀') == 1` at a UTF-16 cost of 2. Slicing a `str` by index cannot split a pair; only slicing UTF-16 *bytes* can, and that fails loudly on decode. This is why 19.4 measures per code point and never slices encoded bytes.
- **`EMPTY_TREE_SHA` is this repo's established idiom** for "no real boundary" (`src/commits/collector.py:23`, already used by `SinceDeployWindow` and `Report`). 18.1 normalizes GitHub's all-zero `before` to it.
- **Task numbers and file order deliberately disagree in two places.** `21.4` is numbered fourth but placed second, because it must run before the reference-dependent work; Phase `22` is numbered last but placed first, before Phase 18. Both carry the reason in their own text. Do not "fix" either.
- **Handoff `09`'s inventory undercounts.** It reports 73 entries across 34 files; the true population is **76 across 59** — it missed `reviews/47-10-2-report-schedules-delivery-review-1.md` entirely, and one of its worked dedup examples conflates two distinct defects. It is a spent record and is deliberately left uncorrected; do not resume from its counts.

## 8. Domain model spine

- **A reference note is authored by a person, never generated.** A generated reference measures the model against itself, which is the exact failure the harness exists to prevent. 21.2's and 21.5's contract lines and specs carry the prohibition as their opening words. Don't re-litigate — `.ai-factory/specs/63-eval-reference-notes.md`.
- **The harness writes output and does not compare.** `EvalRunner.run` never reads `evals/reference/`; a person judges an output against its reference. 21.3 makes a missing reference loud, non-fatally — it adds no diffing. Don't re-litigate — `.ai-factory/specs/64-missing-reference-report.md`.
- **History is never rewritten.** `.ai-factory/plans/`, `plan-reviews/`, `reviews/`, `handoffs/`, the specs of completed tasks, and every `[x]` roadmap line record what happened. The prune clears them in its own time. Don't re-litigate — the user's own ruling.
- **The governing spec may state intended behavior ahead of code.** For unbuilt work a doc legitimately ends at the doc. What is forbidden is a doc that contradicts shipped behavior, or is silent where an implementer must guess. Don't re-litigate — global `CLAUDE.md`, "Grounding claims".

## 9. Hard rules

- Never commit without explicit permission. Commit messages: short noun phrase or imperative, sentence case, no type prefixes, no body for a single-concern commit. The prune's own commit, if it ever runs, is exactly `Roadmap prune`.
- The prune sweeps with `rm` / `find -delete`, never `git rm`; `.ai-factory/handoffs/` is never swept.
- A foreign product's name stays out of live artifacts. Phase 22 removes the last four mentions, in `docs/concepts/product-scope.md` and `docs/concepts/derivation-modes.md`. History keeps its mentions untouched.
- In `docs/concepts/product-scope.md` the second product must stay **unnamed**, not replaced by this organization's own — the argument is that one organization holds two *unrelated* products, and substituting the product it is contrasted with collapses it into a tautology.
- Code and test comments never cite the plan layer — no phase number, no roadmap reference, no `.ai-factory/` path.

## 10. Cross-cutting contracts / invariants checklist

- **The fixed eval window** is `0783684467d191a44bea94aa1de521f2cb23d6df..1bb7597925f54d42184d317c4f5eb2b2fde9aabe` — three commits, each flipping one roadmap task to `[x]`, so a linked change resolves non-empty. Every reference note is written against it. 21.4 replaces the moving `HEAD~3..HEAD` in `herald-recent`, `herald-recent-en`, and `herald-localize` with it; 21.1's new case carries it from birth.
- **Case names are pinned, not chosen at implementation time.** The narrate case is `herald-narrate`, because `evals/reference/herald-narrate.md` already exists and the harness pairs a case with its reference by name alone. A different name orphans the file.
- **The extracted release fan-out class is `ReleaseDelivery`**, living in the existing `src/delivery/service.py` beside `DeliveryService` — not `ReleaseDeliveryOrchestrator`, and not a new file. Both the GitHub-release and changelog-wiring task specs originally named that file; the logic grew in the router instead.
- **`_deliver_release`'s twelve-case behavior suite moves with it.** `tests/ingestion/test_release_delivery.py` pins leg order, the single language-union resolution, graceful degradation at both changelog calls, the prerelease flag, the no-version skip, and the absence of re-derivation. Every case is retargeted at the new class; none is dropped, weakened, or merged — that suite is what proves the extraction changed no behavior.
- **`RepoMirror`'s async conversion genuinely widens its concurrency surface.** Methods that run atomically with respect to the event loop today gain yield points, so interleavings that are structurally unreachable become reachable. `.ai-factory/specs/04-repo-mirror.md` guards that the mirror "introduces no new concurrency surface beyond what 3.1.1 already pinned" — 20.2.1 re-pins it before 20.2.2 converts. Any guard claiming "only scheduling changes" is false.
- **Marker grammar:** append-only, space-separated, at the end of an entry's **final** line; `[dismissed]`, `[fixed]`, `[routed → <path>]` with a U+2192 arrow, never `->`. Entry text and `Affects:` are never rewritten.
- **The manual-task convention**, introduced this session for 21.2 and 21.5: `(manual)` in the task name plus the prohibition as the opening words of both the contract line's description and the spec body, ahead of `## Current state`.

## 11. Per-unit map with watch-points

- **18.1 — creation-SHA normalization** (`specs/53`). Maps an all-zero `before` to `EMPTY_TREE_SHA` inside `_parse_push_event`. *Watch:* the placement is deliberate — normalizing a GitHub webhook convention is parsing, the router's own job, so `Versioner.next` keeps its "specified over resolved SHAs" contract and Phase 20's extraction is untouched. It changes no line in `src/versioning/versioner.py`.
- **18.2.1 / 18.2.2 — collector failure signal** (`specs/65`, `54`). The contract task declares how a `git` failure is signalled distinctly from an empty range and pins it red; the impl greens it. *Watch:* the docstring is rewritten only by the impl task, when the body matches — the contract task leaves it describing today's no-raise behavior.
- **18.3 — on-install backfill** (`specs/55`). Dispatches `KnowledgeSync.backfill` per added repo after `store.add`. *Watch:* the guard about overlapping backfills — the primary key prevents duplication, but an unlucky interleaving can fail one write, and the per-repo isolation wrapper would swallow it, leaving a repo half-indexed with the webhook already acknowledged.
- **19.1 — Telegram token redaction** (`specs/56`). *Watch:* the leak path is concrete and already reachable — the send runs under the router's `_run_isolated`, which catches with a bare `except Exception` and reports through `logger.exception`. Verified against httpx: `HTTPStatusError`'s string form carries the token; a transport error's message does not, but every `RequestError` exposes `.request.url`, which does.
- **19.2 — DSN percent-encoding** (`specs/57`). *Watch:* three test fixtures mirror the same unescaped helper — `tests/episodic/conftest.py`, `tests/graph/conftest.py`, `tests/knowledge/conftest.py` — and all move together. A password with no reserved character must yield a byte-identical DSN.
- **19.4 — UTF-16 chunking** (`specs/59`). *Watch:* measure per code point and cut on code-point boundaries; never slice the encoded bytes. The surrogate hazard then cannot occur by construction rather than being tested for.
- **20.1 — `ReleaseDelivery` extraction** (`specs/60`). *Watch:* behavior-identical, and the twelve-case suite moves without weakening. The changelog base URL becomes a plain attribute read.
- **20.2.1 / 20.2.2 — mirror concurrency contract and async boundary** (`specs/66`, `61`). *Watch:* no `asyncio.run` is added anywhere — every caller already has one, including all four `scripts/*` entrypoints and `main.py`'s `lifespan`. The thread offload lives inside `RepoMirror` once.
- **21.1 — narrate case** (`specs/62`). *Watch:* singular `lang`, the pinned name `herald-narrate`, and the fixed range. Its reference already exists.
- **21.3 — missing-reference report** (`specs/64`). *Watch:* non-fatal, presence-checking only, and it mirrors the shape of the existing unregistered-case-type check while **not** raising as that one does. It adds `tests/scripts/test_eval.py`, the harness's first test module.
- **21.4 — fixed eval ranges** (`specs/67`). *Watch:* it must land before any harness run; until then the cases carry a moving window while every reference is written against a fixed one, and a run would show differences that are not quality problems.
- **22.1 — foreign product name sweep** (`specs/68`). *Watch:* four mentions in two concept documents. The scope document's second product is anonymised, never replaced.
