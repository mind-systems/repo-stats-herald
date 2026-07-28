## Code Review Summary

**Artifact reviewed:** `.ai-factory/plans/26-4-4-historical-backfill.md` (plan for task 4.4 — Historical backfill)
**Files the plan touches:** `src/commits/collector.py`, `src/episodic/store.py`, `src/github/mirror.py`, `src/episodic/backfill.py` (new), `scripts/backfill_episodic.py` (new)
**Risk Level:** 🟢 Low — one internal contradiction to resolve; everything else is well-grounded

### Context Gates
- **Architecture** (`.ai-factory/ARCHITECTURE.md`): PASS. `EpisodicBackfill` is a constructor-DI service that receives abstractions (`Embedder`, `EpisodicStore`) and public classes (`RepoMirror`, `LinkedChangeResolver`, `GitCommitCollector`) and is wired only at a composition root (`scripts/backfill_episodic.py`). This introduces a new `src/episodic/ → src/github/` edge (importing `RepoMirror`), but it is a *public class injected via constructor*, which the dependency rules explicitly permit (the same import already exists in `src/ingestion/writer.py`). No feature-internals reach.
- **Rules** (`.ai-factory/RULES.md`): PASS. File is intentionally empty; no counter-defaults to honor.
- **Roadmap** (`.ai-factory/ROADMAP.md` line 4.4 → `Spec: .ai-factory/specs/26-historical-backfill.md`): PASS. The plan matches the spec on every point — new `src/episodic/backfill.py` with `EpisodicBackfill.run(repo, org_id)`, per-historical-tree evaluation, resolve+embed-only, historical `changed_at`, idempotency, bare-object-store reads (no worktree churn), and the manual entrypoint "same trigger shape as 3.6's backfill". Downstream task 5.4 confirms the class/method names (`EpisodicBackfill.run`) the plan chose. No skill-context override file present.

### Verified assumptions (ground-truth checks)
- **Empty-tree root handling** — Verified against this repo: `git log 4b825dc…4904..<root>` lists the root commit (exit 0), and `git show 4b825dc…4904:<path>` fatals → `LinkedChangeResolver._read_roadmap_at` (uses `check=False`, returns `None` on non-zero) reads it as "no prior roadmap". The uniform `resolve(bare, before, after)` claim for the root holds.
- **First-parent walk format** — `git rev-list --reverse --first-parent --parents HEAD` verified: oldest-first, root line has a single token (commit, no parent), every other line is `<commit> <parent1>`. The plan's "before = first parent when present else empty-tree SHA" is correct.
- **Bare-store operations** — `resolve` (`git show {ref}:{path}`, `git log {before}..{after}`), `GitCommitCollector.collect` (`git log --numstat`, `git rev-parse --abbrev-ref HEAD`), and `commit_timestamp` (`git show -s --format=%cI`) all operate on the injected repo path and work against a `--mirror` bare store — no worktree required. Matches the spec's worktree-avoidance guard.
- **Idempotency by recorded SHA is sound** — For any first-parent step `(before, after)`, `git log before..after` always includes `after`, so `after` lands in that entry's `commit_shas`; on re-run `recorded_commit_shas` contains it and the step is skipped. Live 4.3 pushes record their whole range's shas (including first-parent tips), so backfill correctly skips commits already covered by live writes. Merge side-branch commits are never first-parent tips, so they never appear as an `after` and cannot cause double coverage.
- **Writer parity** — `content`, `commit_shas`, and the `EpisodicEntry` construction in Task 4 mirror `src/ingestion/writer.py` exactly; `EpisodicEntry`/`CommitContext`/`Commit` fields match; `[embedding] = await embedder.embed([content])` matches `OllamaEmbedder`.
- **Composition-root wiring** — Every collaborator and setting Task 5 names (`get_settings`, `create_pool(settings.postgres_dsn)`, `OllamaEmbedder(ollama_url, embed_model, ollama_api_key)`, `PgEpisodicStore`, `AiFactorySourceStrategy`, `GitCommitCollector`, `LinkedChangeResolver`, `GitHubAppAuth`/`clone_source`/`RepoMirror`, `settings.canonical_refs`) exists in `src/main.py`'s lifespan and/or `scripts/backfill.py`, with the config fields present in `src/core/config.py`. Applying `src/episodic/schema.sql` needs no new migration — `recorded_commit_shas` only reads existing columns.
- **Canonical-ref policy** — Task 4 step 2 reproduces `KnowledgeSync._canonical_ref` exactly (`canonical_refs.get(repo)` else `mirror.default_branch(repo)`).

### Critical Issues
None.

### Issues to resolve

**1. Task 1 — `check=True` contradicts the stated "empty/unknown ref yields `[]` (no crash)".** (`src/commits/collector.py`, `first_parent_steps`)
The task says both *"Read-only, `check=True` like the existing methods"* and *"an empty/unknown ref yields `[]` (no crash)"*. These are mutually exclusive: `git rev-list --first-parent --parents <unknown-or-unborn-ref>` exits non-zero (`fatal: ambiguous argument …` / `fatal: bad revision …`, verified against this repo), so with `check=True` the method raises `CalledProcessError` rather than returning `[]`. An implementer following the letter of "`check=True` like the existing methods" will produce a method that crashes on the very input the same sentence promises to handle gracefully. Decide one:
   - use `check=False`, and return `[]` when `returncode != 0` (honors the no-crash contract but diverges from the "check=True" phrasing); **or**
   - drop the "yields `[]` (no crash)" clause and accept that an unknown/unborn ref raises (acceptable in practice — in the Task 4 flow the ref is always the canonical ref resolved *after* `mirror.ensure`, so it exists; the graceful-empty case only matters for a repo with an unborn `HEAD`, i.e. zero commits).
   
   Low runtime impact (the happy path never hits it), but the plan should not hand the implementer a self-contradictory contract.

### Positive Notes
- The empty-tree root reduction to a uniform `resolve(bare, before, after)` call is elegant and, importantly, *verified* in the plan rather than assumed — and it holds up under independent checking.
- Idempotency keyed on the recorded-SHA set (not a `changed_at` watermark) is the correct choice, and the plan's justification (survives interleaving with live 4.3 pushes, resumable after interruption) is accurate.
- Owned-details discipline is respected: the empty-tree constant and all git-command flags stay inside `GitCommitCollector`; the Postgres `unnest` query stays inside `PgEpisodicStore`; the ABC stays Postgres-free.
- Task decomposition is clean — three enabling capabilities (Tasks 1–3), the service (Task 4), the entrypoint (Task 5) — with dependencies stated, and each new method is self-contained and reused rather than duplicated.

## Deferred observations
- Affects: Task 1 (`src/commits/collector.py`) — The existing collector methods (`commit_timestamp`, `_collect_commits`) pass `--end-of-options` before the user-supplied ref/range to prevent a ref that looks like an option from being interpreted as one; the plan's `rev-list` command text omits it. Since refs here are operator-supplied (canonical ref / CLI), the risk is negligible, but matching the established convention (`--end-of-options <ref>`) would keep the new method consistent with its siblings. Left to implementer discretion as it is a git-command detail owned inside the class. [dismissed]
- Affects: Task 4 (`src/episodic/backfill.py`) — The "skip a step with no tasks and no commits" guard is effectively unreachable for a valid first-parent step, since `git log before..after` always yields at least `after`; it is harmless defensive code (prevents embedding an empty string) and worth keeping, just noting it will not fire in normal operation. [dismissed]
