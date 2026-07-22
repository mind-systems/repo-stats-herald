# Plan: 5.4 — Episodic code-derivation

## Context
Extend the historical episodic backfill so a pre-harness step's entry is derived from code via `CodeDistiller` (5.2) instead of falling back to commits-only, while harnessed steps keep using `LinkedChangeResolver` (4.2) — code-derived and artifact-derived entries coexisting along one repo's timeline.

## Settings
- Testing: no
- Logging: minimal
- Docs: no

## Grounding notes (read before implementing)
- Spec: `.ai-factory/specs/35-episodic-code-derivation.md` — the single source for the change; `docs/concepts/derivation-modes.md` for why the mode is chosen per historical tree.
- `EpisodicBackfill.run` (`src/episodic/backfill.py`) today reads the **bare object store by SHA** (`mirror.object_store_path`) and never opens a worktree — a deliberate exception for read-only replay. The code-derivation path must preserve that: read changed blobs by SHA into a scratch dir, never `mirror.tree` (a full checkout per step would accumulate on disk until process exit, per `RepoMirror.tree`'s deferred-reclamation note).
- Harness presence is keyed on the **roadmap**, matching the resolver: `LinkedChangeResolver._read_roadmap_versions` uses `SourceStrategy.roadmap_paths()`, and the spec's current-state says a pre-harness commit is one where "`LinkedChange.resolve` has no roadmap to anchor to." So: roadmap file present at `after` **or** `before` → resolver path (unchanged 4.4 behavior); absent at both → code-derivation path.
- `CodeDistiller.distill(repo, paths, tree)` reads each path from a filesystem `tree: Path` and groups per-module into bounded prompts (`group_units`) — the "bounded units" guard is satisfied by reusing it as-is; do not reimplement grouping.
- Architecture principle (project `CLAUDE.md` / ARCHITECTURE.md): git-command details live in `GitCommitCollector`, not inline in a caller. The new git reads (changed paths, blob content) therefore belong on the collector; `EpisodicBackfill` stays orchestration-only. This is a deliberate, justified widening of the spec's terse "edit `backfill.py`" file list — annotate it as `DEVIATION` in the diff.
- Out of scope: the live push writer (4.3, `src/ingestion/router.py`) — this task touches only the historical replay in `EpisodicBackfill.run`.

## Tasks

### Phase 1: Git-read helpers on the collector

- [x] **Task 1: Add read-only changed-paths + blob reads to `GitCommitCollector`**
  Files: `src/commits/collector.py`
  Add two read-only, never-raising methods that keep git details inside the collector (the encapsulation the backfill's code path needs):
  - `changed_paths(repo_path: str, before: str, after: str) -> tuple[str, ...]` — run `git -C <repo_path> diff --name-only --no-renames --end-of-options <before> <after>` (`--no-renames` so rename arrows don't corrupt paths); return the path lines as a tuple. On non-zero return (an unknown/unborn ref — a two-tree diff does **not** fail on merge commits) return `()` — mirror the existing `first_parent_steps` no-raise contract. Reuse the `check=False` + `returncode` pattern already in this file (`text=True` is fine here — path names are UTF-8).
  - `read_blob(repo_path: str, ref: str, path: str) -> str | None` — run `git -C <repo_path> show --end-of-options <ref>:<path>` and return the blob text, or `None` if the path is absent at that ref **or** the content is not valid UTF-8. **Capture bytes, decode manually** — do NOT use `text=True` here: with `text=True` an invalid-UTF-8 blob raises `UnicodeDecodeError` *inside* `subprocess.run`, before any guard can convert it to `None`, breaking the never-raise contract. So: `subprocess.run([...], capture_output=True, check=False)` (bytes stdout), return `None` on non-zero return, else `try: return result.stdout.decode("utf-8") / except UnicodeDecodeError: return None`. This is the "read blobs by SHA" primitive the object-store doc already describes.
  Both are pure reads against the bare object store — no worktree, no mutation.

### Phase 2: Per-step mode selection in the backfill

- [x] **Task 2: Inject the distiller and strategies into `EpisodicBackfill`** (depends on Task 1)
  Files: `src/episodic/backfill.py`
  Extend the constructor with three DI params (abstractions/concretes injected, never built inside — matches the existing constructor discipline and `CodeBootstrap`):
  - `distiller: CodeDistiller` (from `src.knowledge.code_distiller`),
  - `code_strategy: SourceStrategy` (the `CodeSourceStrategy` concrete, typed as the `SourceStrategy` ABC since only `selects` is used) — for filtering changed paths to source code,
  - `source_strategy: SourceStrategy` (the artifact `AiFactorySourceStrategy`) — used only for its `roadmap_paths()` to probe harness presence.
  Store them; import `CodeDistiller`, `SourceStrategy`. Update the class docstring: the code-derivation path issues per-change LLM generation (the 4.4 "no per-change LLM generation" guard is deliberately relaxed here for pre-harness steps, per spec), still reading blobs by SHA (no worktree).

- [x] **Task 3: Split `run` into a per-step mode decision** (depends on Task 2)
  Files: `src/episodic/backfill.py`
  In the `for before, after in steps` loop, keep the idempotency skip (`if after in recorded`) unchanged, then branch **per step** on harness presence:
  - Add `_harness_present(self, bare, before, after) -> bool`: return `True` if any `self._source_strategy.roadmap_paths()` candidate has non-`None` `self._collector.read_blob(bare, ref, path)` for `ref` in `(after, before)`. Empty `roadmap_paths()` (a code-only strategy) → always `False`.
  - Harness present → the existing resolver path, extracted into `async def _resolve_entry(...)` (it awaits `embed`), behavior byte-identical to today: `resolver.resolve`, `content` from tasks+commit messages, embed, skip if empty.
  - Harness absent → the new `async def _distill_entry` path (Task 4).
  Both branches produce an `EpisodicEntry | None`; a `None` (empty content) increments `skipped` and continues, exactly as today. Preserve the `walked/appended/skipped` counters and the final summary log.

- [x] **Task 4: Implement the code-derivation path `_distill_entry`** (depends on Task 3)
  Files: `src/episodic/backfill.py`
  `async def _distill_entry(self, repo, org_id, bare, before, after) -> EpisodicEntry | None`:
  - Collect commits for the step: `ctx = self._collector.collect(bare, f"{before}..{after}")` (gives commit SHAs and the message fallback; no resolver, no roadmap anchoring).
  - Changed source paths: `self._collector.changed_paths(bare, before, after)` filtered by `self._code_strategy.selects(path)`.
  - Materialize those blobs at `after` into a scratch dir so `CodeDistiller` can read a `tree: Path`: use `tempfile.TemporaryDirectory()`; for each selected path, `content = self._collector.read_blob(bare, after, path)`; skip `None` (deleted at `after`); write to `<tmp>/<path>` creating parents; collect the successfully written repo-relative paths. This stays within the "read blobs by SHA, no worktree" model and cleans up per step.
  - `distilled = (await self._distiller.distill(repo, written_paths, Path(tmp))).strip() if written_paths else ""`.
  - `content = distilled or "\n".join(c.message for c in ctx.commits)` — distilled feature text is the semantic half; fall back to the commit-message floor so a pre-harness non-code commit is not lost (matches today's "skip only when everything is empty"). **Note:** `ctx` is a `CommitContext`, so `ctx.commits` is *already* the `tuple[Commit, ...]` — iterate `ctx.commits`, NOT `ctx.commits.commits` (the double `.commits` is correct only on the resolver path where the variable is a `LinkedChange`).
  - If `not content` → return `None`.
  - `changed_at = self._collector.commit_timestamp(bare, after)`; `[embedding] = await self._embedder.embed([content])`.
  - Return `EpisodicEntry(repo=repo, org_id=org_id, completed_tasks=(), commit_shas=tuple(c.sha for c in ctx.commits), content=content, embedding=embedding, changed_at=changed_at)` — `completed_tasks` empty (no roadmap). The embedding is computed **inside this helper**; the caller only appends the returned entry — identical to the resolver path (each helper embeds, the loop appends; never double-embed in the caller).
  Add the `Path`/`tempfile` imports.

### Phase 3: Composition-root wiring

- [x] **Task 5: Wire the new dependencies in the backfill script** (depends on Task 2)
  Files: `scripts/backfill_episodic.py`
  In `_run`, construct the distiller and code strategy the same way `scripts/bootstrap.py` does, and pass all three new args to `EpisodicBackfill(...)`:
  - `from src.llm.client import OllamaClient`, `from src.knowledge.code_distiller import CodeDistiller`, `from src.knowledge.code_source_strategy import CodeSourceStrategy`.
  - `distiller = CodeDistiller(OllamaClient(settings.ollama_url, settings.ollama_model, settings.ollama_api_key))`.
  - `code_strategy = CodeSourceStrategy()`.
  - The existing `strategy = AiFactorySourceStrategy()` is reused for both the resolver and the new `source_strategy` arg.
  - Call `mirror.sweep_worktrees()` once before `backfill.run` — consistent with `scripts/bootstrap.py`'s startup (harmless here since the code path uses temp dirs, but keeps the mirror-hygiene invariant).
  - `EpisodicBackfill(mirror, resolver, embedder, store, collector, settings.canonical_refs, distiller, code_strategy, strategy)` — match the final constructor parameter order chosen in Task 2.
