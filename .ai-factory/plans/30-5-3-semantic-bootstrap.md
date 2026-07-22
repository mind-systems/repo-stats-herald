# Plan: 5.3 — Semantic bootstrap

## Context
Give a code-only repo a path into the knowledge store: distill its current code into a feature-level draft written to a fixed, source-strategy-excluded path (`.ai-factory/bootstrap-draft.md`) that a human reviews and graduates into a committed selected artifact — never a direct `KnowledgeStore` write and never a re-run clobber of reviewed work.

## Settings
- Testing: no
- Logging: minimal
- Docs: no

## Tasks

### Phase 1: Bootstrap module

- [x] **Task 1: `CodeBootstrap` in `src/knowledge/bootstrap.py`**
  Files: `src/knowledge/bootstrap.py`
  Add `CodeBootstrap` — constructor DI, no concretes built inside (matches `KnowledgeSync` in `src/knowledge/sync.py`):
  ```python
  def __init__(self, mirror: RepoMirror, distiller: CodeDistiller,
               strategy: SourceStrategy, draft_root: Path) -> None:
  ```
  `mirror` = `RepoMirror` (`src/github/mirror.py`), `distiller` = `CodeDistiller` (`src/knowledge/code_distiller.py`), `strategy` typed as the `SourceStrategy` ABC (`src/knowledge/source_strategy.py`) — only `strategy.selects(rel)`, an ABC method, is called, so type the parameter as the abstraction (matching `KnowledgeSync.__init__`'s `strategy: SourceStrategy` and CLAUDE.md's "receive abstractions through their constructor"); the composition root injects the concrete `CodeSourceStrategy()`. `draft_root` = the base directory under which the human-reviewable draft is written (supplied at the composition root — the worktree is ephemeral, so the draft must not live in it). `mirror`/`distiller` stay concrete — those classes have no ABC.

  Own a fixed module-level constant for the draft's repo-relative leaf path — `_DRAFT_RELPATH = ".ai-factory/bootstrap-draft.md"`. This is the single non-selected path bootstrap ever writes.

  Implement `async def run(self, repo: str, org_id: int) -> Path` (returns the written draft path):
  1. `self._mirror.ensure(repo, org_id)` — clone/fetch the bare mirror.
  2. Open `with self._mirror.tree(repo, org_id, "HEAD") as tree:` — an isolated worktree at the mirror's current HEAD (per the spec: HEAD, not 3.6's canonical-ref policy).
  3. Enumerate + filter selected code paths inside the `with`, following the exact pattern in `scripts/eval.py`'s `DistillCaseHandler.run` / `KnowledgeSync.backfill`: `tree.rglob("*")`, skip non-files and any path with `.git` in its parts, compute `rel = path.relative_to(tree).as_posix()`, keep `rel` when `self._strategy.selects(rel)`.
  4. `distilled = await self._distiller.distill(repo, selected, tree)` — the distiller's output is used as-is (the present-tense feature inventory per `docs/concepts/code-derived-understanding.md`); bootstrap adds NO prompting of its own.
  5. Wrap `distilled` in a document frame (`self._frame(distilled)`) and write it. Do all reading/distilling before leaving the `with` (the worktree may be reclaimed after); the file write may happen inside or after.

  `_frame(body: str) -> str`: prepend a title + an unmistakable LLM-generated/unreviewed banner (English, present tense) instructing that the file is an automated draft, is NOT indexed, and must be reviewed and its content copied/adapted into a curated **selected** artifact and committed — this file itself is never committed as-is. Frame text lives in this method, not inline in `run`.

  Draft write target: `draft_path = self._draft_root / repo / _DRAFT_RELPATH`; `draft_path.parent.mkdir(parents=True, exist_ok=True)`; `draft_path.write_text(framed, encoding="utf-8")`. Namespacing by `repo` keeps multi-repo runs from colliding while the fixed leaf stays `.ai-factory/bootstrap-draft.md`. `write_text` truncate-overwrites, so a re-run refreshes the same path — idempotent, no duplication.

  Guards (enforce by construction, not by convention):
  - The ONLY path written is `_DRAFT_RELPATH` under `draft_root`. No `KnowledgeStore`/`PgVectorStore` import or write anywhere in this module; no write to a source-selected path; no write to any committed artifact.
  - Non-selection guard: at construction, verify the default artifact profile does not select the draft leaf and **raise** (not `assert`, which `python -O` strips) if it does — `if AiFactorySourceStrategy().selects(_DRAFT_RELPATH): raise ...` (import `AiFactorySourceStrategy` from `src/knowledge/source_strategy.py`). This pins the spec invariant that 3.6 (which indexes via that profile) can never auto-index the draft, and fails loud if the path ever becomes selectable.
  - `log.info` once on completion (repo, ref, selected-file count, draft path) via the `logging` module — no `print`.

- [x] **Task 2: Composition-root entrypoint `scripts/bootstrap.py`** (depends on Task 1)
  Files: `scripts/bootstrap.py`
  Model this on `scripts/backfill.py` — assembly only, no logic. `argparse` with `--repo` (required) and `--org-id` (required, `type=int`). In `_run(repo, org_id)`:
  - `settings = get_settings()`.
  - Build the mirror as in `backfill.py`: load the App PEM from `settings.github_app_private_key_path`, `auth = GitHubAppAuth(settings.github_app_id, pem)`, the same `clone_source(repo, org_id)` closure over `settings.github_org_logins`, `mirror = RepoMirror(Path(settings.mirror_root), auth, clone_source)`. Then add `mirror.sweep_worktrees()` once before use — this call is NOT in `backfill.py`, but is required here per `RepoMirror`'s docstring: `tree()` defers worktree removal to the next `ensure()` in the same process, so a one-shot script exits before that fires and leaks its scratch worktree; the startup sweep reclaims prior runs' leftovers.
  - `distiller = CodeDistiller(OllamaClient(settings.ollama_url, settings.ollama_model, settings.ollama_api_key))` — mirrors `scripts/eval.py`'s distiller wiring.
  - `strategy = CodeSourceStrategy()`.
  - Choose the draft base directory from a `Settings` field (add `bootstrap_draft_root` to `src/core/config.py` with a sensible default such as `"bootstrap-drafts"`, documented in `.env.example`) rather than a literal — secrets/paths come from `Settings`, never hardcoded in the entrypoint. Pass `Path(settings.bootstrap_draft_root)`.
  - `bootstrap = CodeBootstrap(mirror, distiller, strategy, Path(settings.bootstrap_draft_root))`; `await bootstrap.run(args.repo, args.org_id)`.
  - No DB pool is opened — bootstrap never touches `KnowledgeStore` (contrast `backfill.py`, which does).
  - Module docstring with the run line: `uv run python -m scripts.bootstrap --repo <name> --org-id <id>`.

  `src/core/config.py` change: add `bootstrap_draft_root: str = "bootstrap-drafts"` to `Settings`; add the corresponding commented key to `.env.example`.

  `.gitignore` change (in-scope, same class of edit as `.env.example`/config): the default `bootstrap_draft_root` is a *relative* path, so drafts land inside Herald's own working tree at `bootstrap-drafts/<repo>/.ai-factory/bootstrap-draft.md` — nothing stops a later `git add -A` from tracking a file the spec is emphatic must NEVER be committed as-is. Ignore the output tree the same way `evals/out/*` already is: add under a comment `# Bootstrap drafts (generated, LLM-unreviewed, never tracked)` the line `bootstrap-drafts/`. Keep this directory name in sync with the `bootstrap_draft_root` default. This makes the spec's central "never committed as-is" invariant a construction guard, not a convention.
