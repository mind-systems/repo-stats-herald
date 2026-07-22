# Code Review — 5.3 Semantic bootstrap

**Plan:** `.ai-factory/plans/30-5-3-semantic-bootstrap.md`
**Code changed/reviewed:** `src/knowledge/bootstrap.py` (new), `scripts/bootstrap.py` (new), `src/core/config.py` (mod), `.env.example` (mod), `.gitignore` (mod)
**Read in full for context:** `src/knowledge/sync.py`, `src/github/mirror.py`, `src/github/app_auth.py`, `src/knowledge/code_distiller.py`, `src/knowledge/code_source_strategy.py`, `src/knowledge/source_strategy.py`, `scripts/backfill.py`, `scripts/eval.py`

## Verdict
No correctness, security, or runtime-breakage findings. The implementation matches the plan and the spec (`34-semantic-bootstrap.md`) exactly.

## Correctness — verified against the codebase
- **`CodeBootstrap.run` flow** — `mirror.ensure(repo, org_id)` then `with mirror.tree(repo, org_id, "HEAD")`, enumerate + filter, distill, frame, write. `RepoMirror.tree` is a **sync** `@contextmanager` yielding a `Path`; used with `with` (not `async with`) — correct. `distill` is awaited — correct.
- **Ephemeral-worktree constraint honored** — all reads (`rglob`, `distiller.distill(... , tree)`) happen **inside** the `with` block; the frame + write happen after, using only in-memory strings and the out-of-worktree `draft_root`. No use of the scratch path after the context exits. `tree()` defers removal to the next `ensure()`, which never fires in a one-shot script; `scripts/bootstrap.py` calls `mirror.sweep_worktrees()` at startup to reclaim prior runs' leftovers — matching the `RepoMirror` docstring contract.
- **Enumerate/filter loop** — `tree.rglob("*")`, skip non-files and any path with `.git` in `.parts`, `relative_to(tree).as_posix()`, keep when `strategy.selects(rel)` — byte-for-byte the pattern in `scripts/eval.py:DistillCaseHandler.run` and `KnowledgeSync.backfill`.
- **`distiller.distill(repo, selected, tree)`** — arg order/types match `CodeDistiller.distill(self, repo, paths, tree: Path) -> str`. Empty `selected` degrades cleanly: `group_units([]) → compose([]) → ""`, framed with the banner, no crash.
- **Draft path** — `draft_root / repo / ".ai-factory/bootstrap-draft.md"` resolves to `bootstrap-drafts/<repo>/.ai-factory/bootstrap-draft.md`; `parent.mkdir(parents=True, exist_ok=True)` then `write_text` (truncate-overwrite) makes a re-run idempotent with no duplication. Returns the path.
- **Non-selection guard is load-bearing** — `if AiFactorySourceStrategy().selects(_DRAFT_RELPATH): raise RuntimeError(...)` in `__init__` (not `assert`, so `python -O` can't strip it). Confirmed `AiFactorySourceStrategy().selects(".ai-factory/bootstrap-draft.md")` returns `False` (leaf not in `_ROOT_ONLY`/`_ROOT_OR_AI_FACTORY`, not under `.ai-factory/specs/` or `docs/`), so the guard does not misfire and correctly pins the "3.6 never auto-indexes the draft" invariant against the profile 3.6 uses.
- **No memory-writing path** — `bootstrap.py` imports neither `KnowledgeStore`/`PgVectorStore` nor the pool; `scripts/bootstrap.py` opens no DB pool (contrast `backfill.py`). The single write target is the fixed non-selected draft leaf. Guards enforced by construction, exactly as the spec intends.

## Wiring & config — verified
- **Imports all resolve** — `AiFactorySourceStrategy`/`SourceStrategy` (`source_strategy.py`), `CodeSourceStrategy` (`code_source_strategy.py`), `CodeDistiller`, `RepoMirror`, `GitHubAppAuth`, `OllamaClient` all exist with the used signatures.
- **`GitHubAppAuth(settings.github_app_id, pem)`** — matches `__init__(self, app_id: int, private_key: str)`.
- **`OllamaClient(ollama_url, ollama_model, ollama_api_key)`** — mirrors `scripts/eval.py`.
- **Abstraction typing** — `strategy: SourceStrategy` in the constructor (only `.selects` called); root injects concrete `CodeSourceStrategy()`. `mirror`/`distiller` stay concrete (no ABC). Consistent with `KnowledgeSync` and CLAUDE.md.
- **`bootstrap_draft_root` default `"bootstrap-drafts"`** is consistent with the `.gitignore` entry `bootstrap-drafts/` and the `.env.example` `BOOTSTRAP_DRAFT_ROOT=` key — the "never committed as-is" invariant is enforced by ignore rule, not left to convention. The relative default lands inside Herald's working tree, which the ignore rule covers.

## Notes (non-blocking, no action required)
- `repo` from `--repo` flows into both the clone URL and the `draft_root / repo` path. This is the same trust level as the existing `scripts/backfill.py` (repo also flows into `RepoMirror._bare_path` as `f"{repo}.git"`); the entrypoint is a human-run composition root, so this is consistent with established convention, not a new exposure.
- This run's scratch worktree leaks on disk until the next run's `sweep_worktrees()` reclaims it — a documented, bounded property of the one-shot-script + deferred-reclamation model, not a defect.

REVIEW_PASS
