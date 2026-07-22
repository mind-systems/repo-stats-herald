## Plan Review Summary — 5.3 Semantic bootstrap

**Plan:** `.ai-factory/plans/30-5-3-semantic-bootstrap.md`
**Files reviewed against:** `src/knowledge/sync.py`, `src/github/mirror.py`, `src/knowledge/code_distiller.py`, `src/knowledge/code_source_strategy.py`, `src/knowledge/source_strategy.py`, `scripts/backfill.py`, `scripts/eval.py`, `src/core/config.py`, `src/llm/client.py`, `.env.example`, spec `34-semantic-bootstrap.md`, concepts `code-derived-understanding.md` / `source-strategy-profiles.md`
**Risk Level:** 🟢 Low

### Context Gates
- **Roadmap (`ROADMAP.md` line 62) — PASS.** The plan's `# Plan: 5.3 — Semantic bootstrap` heading resolves cleanly to the `[ ] 5.3` contract line; the line's `Spec:` tag points at `.ai-factory/specs/34-semantic-bootstrap.md`, which the plan faithfully implements (HEAD distill → fixed non-selected draft → no `KnowledgeStore` write → idempotent re-run). Task linkage is intact.
- **Architecture / CLAUDE.md conventions — WARN (one item).** The plan honors the composition-root pattern (concretes wired only in `scripts/bootstrap.py`, no DB pool, `Settings` read once at the root), feature-depends-on-infra, and "secrets/paths come only from `Settings`" (the new `bootstrap_draft_root` field). One convention deviation noted below (abstraction typing).
- **RULES.md — PASS.** File is intentionally empty (no project counter-defaults); nothing to enforce.

### Verified correct against the codebase
- **`RepoMirror.tree(repo, org_id, "HEAD")`** — signature and detached-worktree semantics match `mirror.py`; `HEAD` on a `--mirror` bare clone resolves to the default-branch tip and is refreshed by `ensure`'s `fetch --prune`. The deviation from 3.6's canonical-ref policy is explicitly mandated by the spec ("over the mirror's current HEAD"), so it is conformance, not drift.
- **Enumerate/filter loop** — `tree.rglob("*")`, skip non-files and `.git` parts, `relative_to(tree).as_posix()`, keep when `strategy.selects(rel)` — byte-for-byte the pattern in `scripts/eval.py:DistillCaseHandler.run` and `KnowledgeSync.backfill`.
- **`distiller.distill(repo, selected, tree)`** — matches `CodeDistiller.distill(self, repo, paths, tree) -> str`; output used as-is per the distillation rubric, correct.
- **Non-selection guard** — `AiFactorySourceStrategy().selects(".ai-factory/bootstrap-draft.md")` genuinely returns `False` (leaf is not in `_ROOT_ONLY`/`_ROOT_OR_AI_FACTORY` and does not start with `.ai-factory/specs/` or `docs/`), so the `assert not …` holds and correctly pins the "3.6 never auto-indexes the draft" invariant against the profile 3.6 actually uses.
- **`sweep_worktrees()` before use** — a correct and important addition. `RepoMirror.tree` defers worktree removal to the *next* `ensure()` in the **same process**; a one-shot script exits before that fires, so each run leaks its scratch worktree on disk. The startup sweep is what reclaims prior runs' leftovers, exactly as the `RepoMirror` docstring requires.
- **`OllamaClient(settings.ollama_url, settings.ollama_model, settings.ollama_api_key)`** — matches the constructor and mirrors `scripts/eval.py`.
- **`bootstrap_draft_root` config + `.env.example` key** — consistent with the pydantic-settings + `.env.example` convention.
- **Draft namespacing by `repo`** — the repo-only namespace (no `org_id`) inherits the mirror's own global-uniqueness assumption (`_bare_path = mirror_root / f"{repo}.git"`), so it introduces no new collision surface. No migration is needed (bootstrap never touches Postgres).

### Critical Issues
None.

### Minor Issues
- **Task 1 — inject the `SourceStrategy` abstraction, not the concrete `CodeSourceStrategy`.** The constructor signature types `strategy: CodeSourceStrategy`, but the plan itself says the shape "matches `KnowledgeSync`", and `KnowledgeSync.__init__` takes `strategy: SourceStrategy` (the ABC). CLAUDE.md's stated pattern is "Feature and service classes receive abstractions through their constructor" (`Summarizer` takes `LLMClient`, not `OllamaClient`). Only `strategy.selects(rel)` — an ABC method — is called, so nothing needs the concrete type. Type the parameter as `SourceStrategy` (from `src/knowledge/source_strategy.py`) for consistency; the composition root still injects `CodeSourceStrategy()`. (`mirror: RepoMirror` and `distiller: CodeDistiller` are fine as concretes — those classes have no ABC.)

### Nits (optional, non-blocking)
- The construction-time guard uses `assert`, which is stripped under `python -O`. Runs are invoked via `uv run python -m …` without `-O`, so it holds today; if the guard is meant to be load-bearing rather than a dev sanity check, a raised exception would be more durable. Acceptable as written.
- "Build the mirror exactly as `backfill.py` does … then `mirror.sweep_worktrees()`" is slightly imprecise wording — `backfill.py` does **not** call `sweep_worktrees()`. The plan's addition is correct and desirable (see above); only the "exactly as" phrasing overstates the parallel.

### Positive Notes
- Guards are enforced by construction (no `KnowledgeStore`/`PgVectorStore` import, single fixed write path, static non-selection assertion) rather than by convention — exactly the spec's "by construction, it has no way to touch either" intent.
- Correctly recognizes the ephemeral-worktree constraint: all reading/distilling stays inside the `with`, and the draft is written to an out-of-worktree `draft_root` — a subtle failure mode the plan gets right.
- Clean separation of frame text into `_frame`, honoring "owned details stay inside the owning class."
- Task 2 correctly opens no DB pool, contrasting `backfill.py`, matching the "no new memory-writing path" guard.
