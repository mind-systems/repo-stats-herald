## Plan Review Summary — 5.3 Semantic bootstrap (round 3)

**Plan:** `.ai-factory/plans/30-5-3-semantic-bootstrap.md`
**Files reviewed against:** `src/knowledge/sync.py`, `src/github/mirror.py`, `src/knowledge/code_distiller.py`, `src/knowledge/source_strategy.py`, `src/knowledge/code_source_strategy.py`, `scripts/backfill.py`, `scripts/eval.py`, `src/core/config.py`, `src/llm/client.py`, `.env.example`, `.gitignore`, spec `34-semantic-bootstrap.md`, `ROADMAP.md` line 62, `.ai-factory/RULES.md`, prior reviews `…-plan-review-1.md` / `…-plan-review-2.md`
**Files Reviewed:** 2 (`src/knowledge/bootstrap.py` — new; `scripts/bootstrap.py` — new; plus edits to `src/core/config.py`, `.env.example`, `.gitignore`)
**Risk Level:** 🟢 Low

### Context Gates
- **Roadmap (`ROADMAP.md` line 62) — PASS.** The `# Plan: 5.3 — Semantic bootstrap` heading resolves to the `[ ] 5.3` contract line; its `Spec:` tag points at `.ai-factory/specs/34-semantic-bootstrap.md`, which the plan implements faithfully (distill over HEAD → fixed non-selected draft path → no `KnowledgeStore` write → idempotent re-run). Linkage intact.
- **Architecture / CLAUDE.md conventions — PASS.** Composition-root wiring (concretes only in `scripts/bootstrap.py`, no DB pool), feature-depends-on-infra (`knowledge → github/mirror` is an established edge in `sync.py`), "secrets/paths come only from `Settings`" (new `bootstrap_draft_root`), owned frame text isolated in `_frame`. Abstraction typing (`strategy: SourceStrategy`) matches `KnowledgeSync`.
- **RULES.md — PASS.** Intentionally empty (project surfaced no counter-default); nothing to enforce.
- **skill-context — N/A.** No `.ai-factory/skill-context/aif-review/SKILL.md` present.

### Prior-review items — all resolved
- **v1: inject the `SourceStrategy` abstraction, not the concrete.** Task 1 types `strategy: SourceStrategy` (the ABC), root injects `CodeSourceStrategy()`. ✅
- **v1: `raise`, not `assert` (stripped under `python -O`).** Non-selection guard is `if AiFactorySourceStrategy().selects(_DRAFT_RELPATH): raise …`. ✅
- **v2: missing `.gitignore` entry for the draft output tree.** Task 2 now adds `bootstrap-drafts/` under a comment, mirroring the existing `evals/out/*` convention, and explicitly ties the ignored directory name to the `bootstrap_draft_root` default — turning the spec's central "never committed as-is" invariant into a construction guard. ✅

### Verified correct against the codebase
- **Constructor DI** — `CodeBootstrap(mirror: RepoMirror, distiller: CodeDistiller, strategy: SourceStrategy, draft_root: Path)` matches the `KnowledgeSync.__init__` shape; only `strategy.selects(rel)` (an ABC method) is used, so typing the parameter as the abstraction is correct.
- **`RepoMirror.tree(repo, org_id, "HEAD")`** — signature and detached-worktree semantics match `mirror.py`; `"HEAD"` is a valid ref for `git worktree add --detach`, resolving to the bare mirror's default-branch tip (refreshed by `ensure`'s `fetch --prune`). The deviation from 3.6's canonical-ref policy is spec-mandated ("over the mirror's current HEAD") — conformance, not drift.
- **Enumerate/filter loop** — `tree.rglob("*")`, skip non-files and `.git` parts, `relative_to(tree).as_posix()`, keep when `strategy.selects(rel)` — byte-for-byte the `scripts/eval.py:DistillCaseHandler.run` / `KnowledgeSync.backfill` pattern.
- **`distiller.distill(repo, selected, tree)`** — matches `CodeDistiller.distill(self, repo, paths, tree) -> str`; output used as-is per the rubric. Empty `selected` degrades cleanly (`group_units([]) → compose([]) → ""`), no crash.
- **Non-selection guard** — `AiFactorySourceStrategy().selects(".ai-factory/bootstrap-draft.md")` genuinely returns `False` (leaf not in `_ROOT_ONLY`/`_ROOT_OR_AI_FACTORY`, not under `.ai-factory/specs/` or `docs/`), so the guard never misfires and correctly pins the "3.6 never auto-indexes the draft" invariant against the exact profile 3.6 uses. Checking the repo-relative leaf (`_DRAFT_RELPATH`) — the position a graduated draft would occupy in the target repo — is the right invariant to assert.
- **`sweep_worktrees()` before use** — the method exists in `mirror.py`; `tree()` defers removal to the next same-process `ensure()`, which a one-shot script never reaches, so each run would leak its scratch worktree. The startup sweep reclaims prior runs' leftovers, exactly as the `RepoMirror` docstring requires. Correctly flagged as NOT present in `backfill.py`.
- **Mirror wiring in `scripts/bootstrap.py`** — PEM from `settings.github_app_private_key_path`, `GitHubAppAuth(settings.github_app_id, pem)`, `clone_source` closure over `settings.github_org_logins`, `RepoMirror(Path(settings.mirror_root), auth, clone_source)` — matches `backfill.py` lines 47–56.
- **`CodeDistiller(OllamaClient(settings.ollama_url, settings.ollama_model, settings.ollama_api_key))`** — matches both constructors and mirrors `scripts/eval.py`.
- **`bootstrap_draft_root: str = "bootstrap-drafts"` in `Settings`** — consistent with the sibling `mirror_root: str = "var/mirror"` precedent; `.env.example` already carries `MIRROR_ROOT=` at line 18, so the commented key belongs alongside it.
- **Draft write target** — `self._draft_root / repo / _DRAFT_RELPATH` composes to `bootstrap-drafts/<repo>/.ai-factory/bootstrap-draft.md`; `write_text` truncate-overwrites → idempotent re-run at a stable path, no duplication. The `.gitignore` `bootstrap-drafts/` line covers this default location.
- **No DB pool** — bootstrap opens none, contrasting `backfill.py` (which does), matching the "no new memory-writing path" guard. No migration needed (bootstrap never touches Postgres).
- **No target-file conflicts** — neither `src/knowledge/bootstrap.py` nor `scripts/bootstrap.py` exists yet.

### Critical Issues
None.

### Positive Notes
- Every guard is enforced by construction, not convention: no `KnowledgeStore`/`PgVectorStore` import, a single fixed write path, a load-bearing `raise` non-selection check, and — new in v3 — the `.gitignore` entry that makes "never committed as-is" a construction guard rather than operator discipline.
- Correctly handles the ephemeral-worktree constraint: all reading/distilling stays inside the `with`, and the draft is written to an out-of-worktree `draft_root` — a subtle failure mode the plan gets right, with a well-justified deviation from the spec's literal in-repo draft location.
- Clean separation of frame text into `_frame`, honoring "owned details stay inside the owning class."
- All three accumulated prior-review findings addressed precisely, without over-correcting.

PLAN_REVIEW_PASS
