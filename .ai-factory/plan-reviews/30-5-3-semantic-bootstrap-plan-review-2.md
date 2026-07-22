## Plan Review Summary — 5.3 Semantic bootstrap (round 2)

**Plan:** `.ai-factory/plans/30-5-3-semantic-bootstrap.md`
**Files reviewed against:** `src/knowledge/sync.py`, `src/github/mirror.py`, `src/knowledge/code_distiller.py`, `src/knowledge/code_source_strategy.py`, `src/knowledge/source_strategy.py`, `scripts/backfill.py`, `scripts/eval.py`, `src/core/config.py`, `.env.example`, `.gitignore`, spec `34-semantic-bootstrap.md`, roadmap line 62, `docs/concepts/code-derived-understanding.md`, prior review `…-plan-review-1.md`
**Risk Level:** 🟡 Medium (one in-scope guard gap; everything else verified sound)

### Context Gates
- **Roadmap (`ROADMAP.md` line 62) — PASS.** The `# Plan: 5.3 — Semantic bootstrap` heading resolves to the `[ ] 5.3` contract line; its `Spec:` tag points at `.ai-factory/specs/34-semantic-bootstrap.md`, which the plan faithfully implements (HEAD distill → fixed non-selected draft → no `KnowledgeStore` write → idempotent re-run). Linkage intact.
- **Architecture / CLAUDE.md conventions — PASS.** Composition-root wiring (concretes only in `scripts/bootstrap.py`, no DB pool), feature-depends-on-infra (`knowledge → github/mirror` is already an established edge in `sync.py`), "secrets/paths come only from `Settings`" (new `bootstrap_draft_root`). The v1 abstraction-typing WARN is resolved (see below).
- **RULES.md — PASS.** Intentionally empty; nothing to enforce.

### Prior-review items — all resolved in v2
- **Inject the `SourceStrategy` abstraction, not the concrete.** Task 1 now types `strategy: SourceStrategy` (the ABC from `src/knowledge/source_strategy.py`), matching `KnowledgeSync.__init__` and the "receive abstractions through their constructor" rule; the root still injects `CodeSourceStrategy()`. ✅
- **`raise`, not `assert` (stripped under `python -O`).** The non-selection guard is now `if AiFactorySourceStrategy().selects(_DRAFT_RELPATH): raise …` — durable, not a dev-only sanity check. ✅
- **"Exactly as `backfill.py`" wording.** Task 2 now explicitly states `sweep_worktrees()` is NOT in `backfill.py` and justifies adding it. ✅

### Verified correct against the codebase
- **`RepoMirror.tree(repo, org_id, "HEAD")`** — signature and detached-worktree semantics match `mirror.py`; `HEAD` on a `--mirror` bare clone resolves to the default-branch tip, refreshed by `ensure`'s `fetch --prune`. The deviation from 3.6's canonical-ref policy is spec-mandated ("over the mirror's current HEAD"), so it is conformance.
- **Enumerate/filter loop** — `tree.rglob("*")`, skip non-files and `.git` parts, `relative_to(tree).as_posix()`, keep when `strategy.selects(rel)` — byte-for-byte the `scripts/eval.py:DistillCaseHandler.run` / `KnowledgeSync.backfill` pattern.
- **`distiller.distill(repo, selected, tree)`** — matches `CodeDistiller.distill(self, repo, paths, tree) -> str`; output used as-is per the rubric. An empty `selected` degrades cleanly (`group_units([]) → compose([]) → ""`), no crash.
- **Non-selection guard** — `AiFactorySourceStrategy().selects(".ai-factory/bootstrap-draft.md")` genuinely returns `False` (leaf not in `_ROOT_ONLY`/`_ROOT_OR_AI_FACTORY`, not under `.ai-factory/specs/` or `docs/`), so the guard does not misfire and correctly pins the "3.6 never auto-indexes the draft" invariant against the profile 3.6 actually uses.
- **`sweep_worktrees()` before use** — correct and necessary: `tree()` defers removal to the next same-process `ensure()`, which a one-shot script never reaches, so each run would leak its scratch worktree; the startup sweep reclaims prior runs' leftovers, exactly as the `RepoMirror` docstring requires.
- **`OllamaClient(settings.ollama_url, settings.ollama_model, settings.ollama_api_key)`** — matches the constructor and mirrors `scripts/eval.py`.
- **`bootstrap_draft_root` config + `.env.example` key** — consistent with the pydantic-settings + `.env.example` convention (`mirror_root` is the sibling precedent).
- **Draft namespacing by `repo`** — inherits the mirror's own global-uniqueness assumption (`_bare_path = mirror_root / f"{repo}.git"`); no new collision surface, no migration (bootstrap never touches Postgres).
- **No target-file conflicts** — neither `src/knowledge/bootstrap.py` nor `scripts/bootstrap.py` exists yet.

### Critical Issues
None.

### Issues (should fix in the plan)
- **Missing `.gitignore` entry for the draft output directory — the spec's core "never committed as-is" guard is left to convention.** The default `bootstrap_draft_root = "bootstrap-drafts"` is a *relative* path, so drafts land inside Herald's own working tree at `bootstrap-drafts/<repo>/.ai-factory/bootstrap-draft.md`. Both the spec ("this file itself is never committed as-is"; guards "No clobber, no re-poisoning") and the plan's own frame banner make "never commit the draft" a central invariant — yet nothing prevents a later `git add -A` in the Herald repo from tracking it. The project already establishes exactly this convention for generated outputs: `.gitignore` carries `evals/out/*` with the comment "Eval outputs (generated, not tracked)". The plan enumerates guards it "enforce[s] by construction, not by convention," but this one hazard — the one the spec is most emphatic about — is left unguarded. The plan already edits `.env.example` and `src/core/config.py` for this feature, so adding a `.gitignore` line (e.g. `bootstrap-drafts/`) is the same class of in-scope change and belongs in Task 2. Please add it (and keep the default's leaf/location consistent with whatever pattern is chosen).

### Positive Notes
- Guards enforced by construction (no `KnowledgeStore`/`PgVectorStore` import, single fixed write path, load-bearing `raise` non-selection check) — matching the spec's "by construction, it has no way to touch either" intent.
- Correctly recognizes the ephemeral-worktree constraint: all reading/distilling stays inside the `with`, and the draft is written to an out-of-worktree `draft_root` — a subtle failure mode the plan gets right, and a justified, well-documented deviation from the spec's literal in-repo `.ai-factory/bootstrap-draft.md` location.
- Clean separation of frame text into `_frame`, honoring "owned details stay inside the owning class."
- Task 2 correctly opens no DB pool, contrasting `backfill.py`, matching the "no new memory-writing path" guard.
- All three prior-review findings were addressed precisely, without over-correcting.
