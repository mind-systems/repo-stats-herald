# Handoff — herald-design-and-roadmap-decompose

> **What this is.** The *state* of the work is in the artifacts (roadmap, 23 specs, docs) — this handoff points to them, it does not repeat them. Everything below is the **chat residue**: the reasoning behind every decision, the rejected alternatives, the corrections, the spike numbers, the infra steps, the meta-lessons, the future vision — none of it in any file. It is long on purpose. Read artifacts for *what*; read this for *why* and *how we work*.

## 1. Frame

- Herald (`repo-stats-herald`, `dev` branch) reframed from a commit-summarizer into a **per-project-understanding + feature-progress narrator**.
- Docs rewritten and restructured; roadmap rebuilt into 12 phases.
- **Phases 1–10 decomposed** into 23 atomic tasks + spec notes. Phases 11–12 remain backlog prose.
- No task implemented. Decomposition is uncommitted.

## 2. Read-first map (artifacts hold the state)

- `.ai-factory/ROADMAP.md` — 12 phases; 1–10 decomposed **above `---STOP---`**, 11–12 below.
- `docs/architecture.md` — domain model: intent→change→outcome, seams, **source strategy**, **two engines**.
- `.ai-factory/specs/01–23` — one full spec per task (current-state / change / files & types / guards / verify).
- `docs/spec/{ingestion,understanding,narration,delivery,configuration}.md` + `docs/spec-overview.md`.
- `docs/concepts/source-strategy-profiles.md` — forward-looking plugin concept.
- `CLAUDE.md` — operational guide + first-time DB setup + docs index.
- `~/projects/01-cross-project-llm-foundation.md` — the cross-project vision (RU, for the user).

## 3. Current state

- Phases 1–10 decomposed (above `---STOP---`); **11–12 NOT decomposed**.
- No task 2.1–10.2 is coded.
- **Uncommitted working tree:**
  - modified: `ROADMAP.md`, `CLAUDE.md`, `docs/architecture.md`, `docs/spec/configuration.md`, `docs/spec/understanding.md`
  - untracked: `.ai-factory/specs/` (23 notes), `docs/concepts/`
  - intentionally untracked: `.env.dev` (gitignored), `~/.secrets/*.pem` (outside repo)
- Commits landed this session: `0f4e8bd` (spec docs), `0869a7d` (serve-allowlist), `33da4a2` + `8608d23` ("Roadmap update"). `dev` pushed once, ahead of origin.

## 4. Next step

- User drives **phase-by-phase**: they type a bare number ("11") to decompose the next phase.
- Likely next: **decompose Phase 11 (Production deployment)**, or they commit first via `/command-commit-roadmap-update`.
- Never auto-commit or auto-implement.

## 5. Working discipline (chat-only — how the user actually operates)

- **The decompose loop (ran for phases 2–10):**
  1. user types a phase number
  2. agent presents an **Atomicity-Gate-checked task draft** with explicit flags (dependencies, what's deferred to which later phase, any cross-repo concern)
  3. user replies "ок" (sometimes after a correction)
  4. agent writes the spec note(s), inserts `### Phase N` + task bullets **above `---STOP---`**, deletes that phase's backlog prose
  5. agent verifies links/anchors/spec-existence with a grep
  6. repeat for the next number
- **Draft-then-confirm** on anything with judgment; **execute immediately** on unambiguous directives ("делай", "сделай апдэйт", "поехали", "прописывай только X", "слей").
- **Commit only when explicitly asked** — they run `/command-commit-roadmap-update` or say "закоммить"/"пуш". They batch-commit periodically as `Roadmap update`. Never auto-commit; never push unless told.
- **They steer by in-the-moment correction** and *value* the agent staying loose rather than rule-bound. Explicit: do NOT convert a soft preference into a measured per-turn gate.
- **They think out loud and escalate scope mid-thread** ("а что если…", "хочу видеть…", "у меня идея"). Engage as a design partner.
- **They reward honest pushback and dislike sycophancy.** When they float a big idea, give a real yes/no with reasons, name the hard parts, then a recommendation — do not just agree.
- **They dislike duplication** ("one home per fact") — across files and across this handoff (they told me: don't restate artifacts, capture the chat residue).
- **They dislike padding but also thin handoffs** — the resolution is dense chat-residue, not restated state, and *line-broken* not wall-of-text.
- Plan-only default: chat plans, orchestrator implements. Every write this session is a planning artifact, doc, or infra config — no app code.

## 6. Error log (mistakes + exact fixes)

1. **400-char "pink elephant."**
   - Agent built a per-turn Python checker for phase-intro length (≤400) and trimmed *good* prose to hit it, obsessing over many turns.
   - User: "400–600 не важно, стало твоим розовым слоном."
   - Fix: dropped the fixation; length is judgment. Mechanism dissected in §B1.
2. **Conflated "mirror" with "engine."**
   - Agent called the repo mirror "the generic engine."
   - User: the *engine* is the **source-selection strategy** (which files define a project); the mirror is dumb plumbing.
   - Fix: elevated `SourceStrategy` to first-class + named the **two engines** in `docs/architecture.md`; renamed task 3.4, specs `04` and `07`.
3. **Negative self-description.**
   - Wrote "Herald doesn't translate commits" → the model latches on & defends the negated thing.
   - Fix: positive framing ("Herald narrates from an understanding of each project"). Rule: never describe behavior by negation.
4. **Letter placeholders.**
   - "feature X advanced; unblocks R and L in Z" — letters read as real entities / a fixed count of two.
   - Fix: role-words ("the feature that advanced … the projects it unblocks").
5. **Cyrillic "ТЗ" in an English CLAUDE.md** read as "T3". Traced to the aif-docs skill's own jargon. Fix: "the full spec".
6. **API-fetch vs local clone (Phase 3).**
   - First decomposed 3.1 as a Contents-API client (`get_file`/`list_paths`).
   - User: why not check out repos locally?
   - Fix: rewrote to `RepoMirror` (git clone/pull); reasoning in §C1. Spec renamed `04-installation-token-content-client.md` → `04-repo-mirror.md`.
7. **sparse-checkout over-engineering.**
   - Agent proposed `--filter=blob:none`+sparse to save disk.
   - User: that leaks per-project "what matters" policy into the *generic* mirror.
   - Fix: full clone; selection stays in `SourceStrategy` above.
8. **Phase 10 external dependency.**
   - Agent included a "hand-integrate mind_api endpoints + E2E" task.
   - User: **only our responsibility, no dependence on external factors.**
   - Fix: dropped it; Phase 10 = client + frozen contract + wiring, verified against a **stub**; phase renamed "Internal protocol (changelog channel)".
9. **Bad first webhook secret** `40)7\@yC8S/0` (shell/make-hostile chars) — flagged the escaping risk; user replaced with a hex secret.
10. **This handoff:** v1 too thin (129 lines), v2 over-compressed to pointers, v3 = exhaustive chat-residue, line-broken.

## 7. Orientation (traps / confusables)

- **Two ARCHITECTURE docs on purpose:** `.ai-factory/ARCHITECTURE.md` = code-organization pattern (feature-modular + DI). `docs/architecture.md` = domain architecture. Never merge.
- **Two meanings of "engine":** the **source strategy** (the "engine" the user means — file selection, per-project) vs the **two builder engines** (knowledge → RAG; changelog → narration). This exact conflation was error #2.
- **Two spec-note dirs:** `.ai-factory/notes/01–07` (Phase-1's) vs `.ai-factory/specs/01–23` (phases 2–10). New specs continue from 24 in `specs/`.
- **The overview file is `docs/spec-overview.md`** — in `docs/`, NOT `docs/spec/`, NOT `overview.md`/`index.md`/README. The user made me rename it twice; do not "fix" it.
- **Graphify PyPI package = `graphifyy`** (double-y); CLI `graphify`. `graphify update` drops `graphify-out/` **inside the target repo** (not gitignored) — always move it out.

## 8. Domain spine — don't re-litigate (in artifacts; here only the flag + the *why* that never got written)

- **Trigger = App signed webhook, not per-repo `herald.yml`** — one org-wide signed webhook beats a workflow in every repo; the Actions idea in the *old* handoff is superseded. (`ingestion.md`)
- **Serve-allowlist by org id, fail-closed** — a public App (needed for >1 org) means anyone can install it; installation ≠ obligation. Two layers: GitHub scopes *repos*, Herald decides *orgs*; org id travels in the payload. (`ingestion.md#who-herald-serves`)
- **Repo mirror is GENERIC (full clone, no sparse/filter)** — per-project file selection belongs to `SourceStrategy` above the plumbing. (`understanding.md`)
- **Declared cross-project links are NOT in the graph** — they surface via RAG; the graph holds only *undeclared* (config) + *coordination-root-seeded* edges (`source=config` never overwritten by `seed`). Empirically justified by the Graphify merge spike (§D). (`understanding.md#project-graph`)
- **No surface-heuristic for forest** — neighbors come from retrieval + graph, never a "is this a contract surface?" guess (that guess is where hallucination starts; the user pushed hard here). (`narration.md#cross-project-narration`)
- **Language is a channel property with configured defaults** (Telegram RU / GitHub EN / app-declared) — each *fixed* channel is single-language; only the app store carries several; a language is generated once and reused; NOT hardcoded (movable to DB/per-org). (`delivery.md`)
- **Versioning:** staging mirrors the release version with `-rc`; back-merge (incoming SHAs already on default) skips the bump; increment is a config point (default `patch`). (`delivery.md#versioning`)
- **Internal protocol: no API keys** — the internal network is the trust boundary (holds while co-located; per-app keys are the multi-tenant future). (`delivery.md#internal-protocol`)
- **Buy commodity plumbing, build the domain, don't adopt an opinionated product as base.** (§C2)
- **Multi-tenant + GUI + per-app keys deferred** (single-node, co-located now). (`configuration.md`, Phase 12)

## 9. Hard rules (beyond global/project CLAUDE.md)

- Standard rules (commit-on-permission, English artifacts, memory triggers, commit-message style) are in the global CLAUDE.md — not repeated.
- **Two-tier + Atomicity Gate** decompose contract; the **above-`---STOP---`** phase-move mechanic (orchestrator only processes above-stop tasks). New specs → `.ai-factory/specs/`, numbering from 24.
- **`*.pem` gitignored; secrets in `~/.secrets/`; `.env.dev` gitignored; `.env.example` documents empty keys; secret *values* never in git — only key names are shared across environments.**

## 10. Cross-cutting contracts / invariants

- Fully in the specs (env vars, seam interfaces, key types, the auth-token chain, the `chunks` schema, `contract/changelog.openapi.yaml`). Not duplicated — grep `.ai-factory/specs/`.
- The one rule to hold: **every external backend sits behind a seam wired only at the composition root** — `LLMClient`, `Embedder`, `KnowledgeStore`, `RepoMirror`/`GitHubAppAuth`, `ProjectGraph`, `SourceStrategy`, `DeliveryPlanResolver`, `TelegramClient`, `Versioner`, `ChangelogClient`.
- The engine is **assembled from these seams**, not rebuilt — many tasks reuse Phase-1 `GitCommitCollector` (on the mirror) and Phase-3 `KnowledgeStore.query(repo=None)`.

## 11. Per-unit map

- Phases 1–10 + tasks are `ROADMAP.md` above-stop + `.ai-factory/specs/01–23`; per-task watch-points are each spec's Guard/Verify. Not duplicated.
- Chat-only cross-phase notes:
  - the mirror is the *accumulator* for weekly (Phase 8) and release (Phase 9) — no separate window store;
  - the language **union (RU+EN)** and release **accumulation since last deploy** first land in Phase 9, not earlier;
  - delivery channels are independent — an unmapped/unreachable app never blocks Telegram or the GitHub release.

---

## A. Session arc — the full map of what we went through

1. **GitHub App provisioning** (walked the user through the UI):
   - permissions = `contents: write` (there is **no separate "releases" permission** — release+tag creation is under Contents write; the old CLAUDE.md said `releases: write`, corrected), `metadata: read`, `pull_requests: read`;
   - **Callback URL left empty** (no user-OAuth flow — Herald acts as the App, not on behalf of a user);
   - **webhook set inactive** ("Subscribe to events" only appears when the webhook is Active; fine to leave off until the receiver exists);
   - "Where can this be installed" = **Any account** (required to serve >1 org);
   - Push event must be **manually checked** once Contents is granted (it's not auto).
2. **Private key + tokens:**
   - generated the `.pem` (one-time download), moved to `~/.secrets/repo-stats-herald.pem` (600);
   - explained the **token chain**: `.pem` → App JWT (~10 min) → installation access token (~1 h, per-org, cached, doubles as git credential); no static token by design.
3. **Env files:**
   - `.env.dev` (gitignored, real values) vs `.env.example` (committed, empty documented keys);
   - principle: share the *key name*, never the *value*; prod secrets from the server store;
   - added `GITHUB_WEBHOOK_SECRET`, `SERVE_ALLOWLIST=244165546`, `GITHUB_APP_ID=4245594`, key path, `POSTGRES_*`; `.gitignore` gained `*.pem`.
4. **Delivery-model corrections (early):**
   - language is a **channel** property, not a repo one;
   - GitHub release = **EN** (was unstated); Telegram = **RU**;
   - changelog store fires **only if repo→app mapped** (matrix wrongly showed it unconditional);
   - default release branch is `master` **or** `main`;
   - permissions corrected to `contents: write`;
   - languages are **configured defaults** (movable to DB), not hardcoded; each fixed channel single-language.
5. **Docs overhaul:**
   - rewrote `CLAUDE.md` concept-dump → operational (modeled on mind_api/mind_mobile CLAUDE.md);
   - generated `docs/spec/` as a governing-TZ;
   - renamed the entrance file through **README → index → `spec-overview.md`** at the user's insistence, moved specs into `docs/spec/`;
   - **removed the doc index from README** (index lives in CLAUDE.md);
   - later **collapsed 10 spec files → 5** by theme (understanding, narration, delivery each merge several);
   - added `docs/architecture.md` (domain level) and `docs/concepts/`.
6. **Roadmap rebuild:**
   - re-outlined the backlog into 12 phases as the vision escalated;
   - reordered so the ingestion foundation is **Phase 2** (the user was tired of "gated on Phase 4");
   - renamed Phase 3 → "Knowledge engine", Phase 5 → "Changelog engine".
7. **Vision escalation** (the core, §F): forest/cross-project → "build a RAG per project" → linked to **Mind biodata** and **Tradeoxy** → the **cross-project foundation** insight (written to `~/projects/01-…`).
8. **Spikes** (§D): Ollama A/B; Graphify on mind_mcp / tradeoxy_broker / core + merge; mempalace + graphify harness inspection.
9. **Clone/mirror pivot + source-strategy elevation** (errors #6–7, #2).
10. **Decomposition of phases 1–10**, one bare number at a time.

## B. Deep durable lessons (chat-only — the user explicitly valued these)

1. **Why rules become "pink elephants."**
   - A rule becomes an obsession when it's turned into a *repeating measured pass/fail loop in live context* AND the agent's own prior outputs keep reaffirming it (self-consistency).
   - The `roadmap-decompose` 1000-char rule never obsesses because nobody measures it — soft guidance framed by purpose. The 400 obsessed because the agent wrote a checker and re-ran it every turn.
   - Amplifiers: instrumentation; self-reinforcement; binary-checkability (you *can* demonstrate exact compliance, so the RLHF compliance-drive latches).
   - Levers: frame constraints by *purpose* not a number; steer by in-the-moment correction (this is *why* the user's correction-based style works — it keeps the agent in judgment mode); the tell = the agent printing a metric's pass/fail every turn; one word ("use judgment") defuses it.
2. **Never describe behavior by negation** ("doesn't X") — the model foregrounds and defends X. Positive present-tense only.
3. **Same family:** literal placeholders (letters), cyrillic jargon in English docs — the model over-indexes on the most concrete, checkable, repeated token; concrete+measured = sticky, abstract+purpose-framed = background.
4. **Abstract rules are noise** — the user's stated reason for *banning memory writes*: a rule that fits everything fires on nothing; value is the concrete case caught in the moment. (Why this handoff avoids abstract restatement.)
5. The user wanted to internalize the pink-elephant mechanism and the "negative self-description" naming but **declined to file them** (per lesson 4) — kept them in their head.

## C. Design debates & rejected alternatives (the reasoning, not just the outcome)

1. **Clone vs Contents-API vs sparse (Phase 3 mirror):**
   - chose **full local clone**: reuses Phase-1 `GitCommitCollector`; makes `git diff` / roadmap `[ ]→[x]` / back-merge detection trivial local ops (simplifies phases 5 & 9); the installation token doubles as the git credential; the mirror stays a *generic* engine;
   - rejected Contents-API: per-file fetch, more calls, can't reuse the collector;
   - rejected `--filter=blob:none`+sparse: saves disk but forces per-project file-selection into the plumbing (wrong layer — user caught this);
   - accepted cost: whole-repo disk, mutable local state, persistent volume; `--depth` is a later global tuning knob, never a selection choice.
2. **Buy vs build vs adopt (mempalace / graphify):**
   - buy commodity plumbing (pgvector + Ollama embeddings + code-graph tooling), **build the domain** (strategy/engines/narrator), **don't adopt an opinionated product as base** — it's someone else's problem-shape and won't transfer to Mind/Tradeoxy;
   - "using a tool teaches the tool; building the seam teaches the domain";
   - steal *patterns* (mempalace's verbatim+scoped+pointer→drawer + its pgvector backend; graphify's `EXTRACTED`/`INFERRED` confidence) behind our own seams.
3. **Postgres+pgvector vs vector-DB vs sqlite-vec:**
   - one *relational* store with vector support beats a vector-DB with config bolted on (relational needs — registry, edges, allowlist, digest state — are the harder half to fake; adding vectors to Postgres is a mature extension);
   - pgvector over sqlite-vec because the user already runs Postgres in dev;
   - behind a `KnowledgeStore` seam so a time-series backend can replace it for Mind's biodata.
4. **Graph = declared-via-RAG + undeclared-config + seeded, not code-graph merge** — the Graphify merge spike proved code-graph merge can't bridge a cross-language proto contract.
5. **Forest = retrieval + graph, no surface heuristic** — the user rejected "decide if this is a contract surface then walk edges" as a hallucination vector.
6. **Phase 10 = our side only** — app-side endpoints and integrator problems are external; "we do everything we can; solve integrator issues as they arise"; verify against a stub; freeze `contract/changelog.openapi.yaml` so any project can integrate.
7. **Two engines over one source strategy** — the realization that the *selection* (which files define a project) is the real engine, per-project, feeding both the knowledge builder (→RAG) and the changelog builder (→narration); the mirror is plumbing. Plus a **deferred plugin system of profiles** (`docs/concepts/source-strategy-profiles.md`) — do NOT build it until a second harness shape forces it.

## D. Spike results (never written to any artifact)

- **Ollama summarization A/B** (`qwen2.5:14b`, over the SSH tunnel):
  - commits-only summary drowned in bookkeeping (`.ai-factory` edits, "roadmap updated");
  - the **roadmap-anchored** summary framed by delivered value and dropped the noise *for free* (the anchor is the completed task, so meta-commits fall away without a classifier);
  - this is the empirical basis for Phase 5's roadmap-anchoring;
  - server was down then fixed; **`make tunnel` dropped twice** — re-run it if a dev LLM call fails.
- **Graphify** (offline AST, MIT):
  - `mind_mcp` at repo-root = 931 nodes / 965 edges but **~67% noise** (381 `.ai-factory` + 247 `.agents`), only 183 real `src/` → **scope to code**;
  - `tradeoxy_broker/Sources` (144 Swift) = 1691 / 4478, 100% code, hubs = real subsystems (StrategyDispatcher, PLR, ProductionBroker…);
  - `tradeoxy_core/src` = 2203 / 5687;
  - **`merge-graphs` broker+core = pure union + a `repo` tag, 0 real cross-project bridges** — the proto contract is `Tradeoxy_V1_OrderUpdate` (Swift) vs `OrderUpdate` (TS), so code-graph merge *cannot* see the link (only 43 coincidental generic-method overlaps);
  - → confirms the declared-edges-via-docs + registry design; code-graph merge is the wrong tool for forest;
  - Graphify commit-pins its graph and `update` re-extracts incrementally (mirrors our git-tied freshness);
  - outputs preserved at `~/projects/tmp/gfx-mind/`.
- **Doc-harness comparison** (evidence for "depth follows what a project exposes" + the profiles concept):
  - ai-factory (mind/tradeoxy) = layered governing spec → deepest;
  - **mempalace** = Claude-manifesto `CLAUDE.md` (verbatim/incremental/local-first principles) + scattered eng docs + RFCs, no ARCHITECTURE, no `.ai-factory` → mid;
  - **graphify** = README-centric (851-line README, ~40 translations, assets) + tiny ARCHITECTURE, **no `CLAUDE.md`** → behavior-rich but progress-thin.

## E. Infra & credentials (chat-only specifics + gotchas)

- **GitHub App:** id `4245594`; org `mind-systems` id `244165546` (from public API); webhook secret + App id + key path in `.env.dev`; key `~/.secrets/repo-stats-herald.pem` (600, outside repo). Webhook **inactive** — enable with a real URL / smee.io / cloudflared when the Phase-2 receiver exists (ngrok free rotates its URL → avoid). App should be "Any account".
- **pgvector gotcha:** built **from source against `postgresql@17`** (the *running* server on :5432) because `pg_config` in PATH resolves to **v14** (both majors installed via brew) — `brew install pgvector` would build for v14 and `CREATE EXTENSION vector` would fail on v17. Recipe in `CLAUDE.md` first-time-setup. Provisioned: role `herald_username`, db `herald_database`, pgvector 0.8.4, extension enabled, TCP login verified.
- **Billing sanity** (the user worried): GitHub Apps consume **no paid seat**; via the App webhook (not Actions) **no Actions minutes**; the "3 devs on private repos" limit is a myth. Reassure if it recurs.

## F. Future directions beyond Herald (expands the foundation note)

- The vision is in `~/projects/01-cross-project-llm-foundation.md`; the chat-only specifics:
- **The unifying primitive** the user articulated: a linked **`intent → signal → outcome`** triple, per subject, over time:
  - Herald: roadmap-task → commits → shipped feature;
  - Mind: instruction → biofeedback → progress;
  - Tradeoxy: strategy-signal → trade → P&L;
  - plus **reference sets** (declared/inferred; meditation reference patterns; baseline strategies) and a **standing per-subject model** updated incrementally.
  - Herald is the *first carrier*; the architecture (seams) transfers, the backends swap.
- **Mind biodata agent:**
  - the user wants a conversational agent over a user's **years** of BCI (neiry) biodata, plus a **real-time biofeedback instructor** (closed loop — adjust the exercise mid-session by performance);
  - storage is real and inspected: `mind_api` `bio_session_samples.samples` jsonb, ~**4.26M** samples, **5 sampleTypes**:
    - `cardio` (heartRate, optional hrv rmssd/sdnn/pnn50/lf/hf/lfhf),
    - `rr` (intervalMs),
    - `nfb` (EEG δ/θ/α/smr/β),
    - `emotions` (attention/relaxation/cognitiveLoad/cognitiveControl/selfControl),
    - `motion` (accel ax/ay/az + gyro gx/gy/gz);
  - envelope `{timestamp, sampleType, data}`, source `neiry`; `session_stream_samples` holds the **instructions/events** — the paired *stimulus*, so instruction↔biofeedback = the same triple as commit↔task;
  - proto `module_biometric_stream.proto` owned by mind_api, `data` an untyped `Struct` by design; mobile has a `BioSample` envelope + typed models;
  - **critical caveat:** biodata is dense numeric **time-series, not text** → the `KnowledgeStore` seam swaps to a DSP/time-series backend; the *architecture* transfers, the store does not; Mind also adds a **closed real-time loop** Herald/Tradeoxy don't have.
- **Tradeoxy:** same triple over trades/strategies; reference = baseline strategies; data structured-numeric.
- **Discipline (repeated and agreed):** build Herald's seams clean; **extract the shared cross-domain abstraction only when Mind actually forces it** — never pre-abstract into a speculative framework. One instance done right; the second teaches what's common.
