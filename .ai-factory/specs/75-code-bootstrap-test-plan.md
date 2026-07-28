# CodeBootstrap — Test Plan

**Date:** 2026-07-29
**Source:** roadmap-test-coverage agent

## Source Overview

`CodeBootstrap` (`src/knowledge/bootstrap.py`) distills a code-only repo's current HEAD into a human-reviewable draft: it calls `RepoMirror.ensure`, opens a `RepoMirror.tree(repo, org_id, "HEAD")` worktree, walks it with `rglob("*")` keeping only files whose repo-relative posix path the injected `SourceStrategy` selects (skipping anything with a `.git` path part), awaits `CodeDistiller.distill`, wraps the result in an unreviewed-draft banner via `_frame`, and writes exactly one file at `draft_root/<repo>/.ai-factory/bootstrap-draft.md`. The constant `_DRAFT_RELPATH = ".ai-factory/bootstrap-draft.md"` is the only path it ever writes, and `__init__` raises `RuntimeError` if `AiFactorySourceStrategy().selects(_DRAFT_RELPATH)` is ever true. Per `.ai-factory/specs/34-semantic-bootstrap.md`, the governing guard is that bootstrap writes **only** the non-selected draft path — never a source-selected path, never the committed reviewed artifact, and never `KnowledgeStore` directly.

## Instantiation

`CodeBootstrap(mirror, distiller, strategy, draft_root)` — four constructor params, no store, no pool, no embedder. Everything below is a hand-rolled fake; nothing here needs Postgres, git, or an LLM.

- **`FakeMirror`** — duck-type of `RepoMirror`. `ensure(repo, org_id)` appends to `self.ensure_calls`. `tree(repo, org_id, ref)` is a `@contextlib.contextmanager` that records `(repo, org_id, ref)`, sets `self.tree_open = True`, yields a pre-populated `tmp_path` subdirectory, and in `finally` sets `self.tree_open = False` **without deleting the directory** — the real `RepoMirror.tree` defers `git worktree remove` to the next `ensure()`, so a fake that `rmtree`s on exit would model the wrong contract.
- **`FakeDistiller`** — `async def distill(self, repo, paths, tree) -> str`; records `(repo, list(paths), tree)` plus `tree_open_at_call` read off the mirror, and returns a canned body from a list (so a second `run` can return a different body). Never subclass `CodeDistiller` — it would drag in `LLMClient`.
- **`strategy`** — two flavors. Use the real `CodeSourceStrategy()` only where end-to-end scoping is the point; use a `RecordingStrategy(SourceStrategy)` whose `selects` returns `True` for everything and appends each argument, where the point is traversal/`.git` filtering (a real strategy would mask the `.git` branch by rejecting those paths anyway).
- **`draft_root`** — always `tmp_path / "drafts"`; never the repo, never `settings.bootstrap_draft_root` (default `"bootstrap-drafts"`, CWD-relative).
- **Async** — `pyproject.toml` sets `asyncio_mode = "auto"`, so `async def test_...` needs no marker.
- **Do not import `tests/knowledge/conftest.py` fixtures** (`pg_pool`, `store`, `make_chunk`) — they open a real Postgres pool. Bootstrap tests must stay DB-free.
- **Import the constant, don't retype it:** `from src.knowledge.bootstrap import _DRAFT_RELPATH`. A copied string literal would keep the invariant test green after someone edits the constant — exactly the silent failure this plan exists to prevent.

## Existing Coverage

- `tests/knowledge/test_code_source_strategy.py` — per-path selection rules for `CodeSourceStrategy`, plus a disjointness check against `AiFactorySourceStrategy`. **Do not re-test selection rules here.**
- `tests/knowledge/test_code_distiller_contract.py` — `group_units` partitioning/ordering and `compose` determinism against a `FakeLLMClient`. **Do not re-test grouping, prompting, or composition here.**
- No test file exists for `src/knowledge/bootstrap.py`. Nothing currently asserts that `_DRAFT_RELPATH` is outside every strategy's selected set.

## Test Cases

### The write-guard invariant (`_DRAFT_RELPATH` × both strategies)

This is the strongest test in the area — the one that catches the silent failure. If the draft path ever became one a source strategy selects, `KnowledgeSync.on_push` would auto-index an unreviewed LLM draft on the next canonical-ref push. No exception, no crash, poisoned memory.

- **should not be selected by either source strategy when `_DRAFT_RELPATH` is fed to both `CodeSourceStrategy().selects` and `AiFactorySourceStrategy().selects`.** Setup: import `_DRAFT_RELPATH` from the module; assert both calls return `False` with a message naming the auto-index consequence. Note the constructor guard checks *only* `AiFactorySourceStrategy` — `CodeSourceStrategy` is the uncovered half, and a future edit there would pass construction silently.
- **should still be unselected when the draft path is seen with its `<repo>/` prefix**, i.e. feed `f"{repo}/{_DRAFT_RELPATH}"` to both strategies. Same invariant for the case where `draft_root` is ever pointed inside a mirrored/served tree.
- **should raise `RuntimeError` naming the draft path when the draft path is ai-factory-selected.** Exercises `__init__`. Setup: `monkeypatch.setattr("src.knowledge.bootstrap._DRAFT_RELPATH", ".ai-factory/specs/leak.md")` *before* constructing — the guard reads the module global at construction time.
- **should construct without raising when the real strategies are used** — the guard's happy path, so a future over-eager guard can't brick normal construction.

### `__init__` — dependency surface

- **should expose exactly `(mirror, distiller, strategy, draft_root)` and no knowledge-store dependency.** Structural: `inspect.signature(CodeBootstrap.__init__).parameters` names equal the expected tuple; and no stored attribute has a `query`/`upsert`/`delete_by_source` attribute. This is the enforceable form of the spec's "no direct write to `KnowledgeStore`" guard — it fails loudly the moment someone threads a store in.

### `run` — traversal and scoping

Shared setup: a fake worktree under `tmp_path` containing `src/a/one.py`, `src/a/two.py`, `src/pkg/mod.ts`, `tests/test_x.py`, `node_modules/left-pad/index.js`, `dist/bundle.min.js`, `README.md`, `.git/config`, `.git/modules/src/nested.py`, plus at least one empty directory.

- **should pass only strategy-selected, repo-relative posix paths to the distiller when the worktree mixes source, test, vendored and generated files.** With the real `CodeSourceStrategy`. Assert set equality, not order (ordering is `group_units`' job, already covered).
- **should never offer any `.git`-internal path to the strategy when the worktree contains `.git/modules/src/nested.py`.** Non-obvious: use the select-all `RecordingStrategy` here — with the real `CodeSourceStrategy` this branch is invisible because those paths would be rejected anyway.
- **should never offer a directory to the strategy when the worktree contains empty and nested directories.** Again needs the select-all recording strategy, since `rglob("*")` yields directories too.
- **should distill from `"HEAD"` after ensuring the mirror, when `run` is called.** Assert `mirror.ensure_calls == [(repo, org_id)]`, `mirror.tree_calls == [(repo, org_id, "HEAD")]`, and that ensure was recorded before the tree open.
- **should invoke the distiller while the worktree is still open.** Assert `fake_distiller.tree_open_at_call is True` and that the `tree` argument the distiller received is the yielded worktree path. Guards against a refactor that moves `distill` out of the `with` block.
- **should write the draft and still succeed when no file in the worktree is selected** (empty repo / docs-only repo). Assert `distill` was called with an empty path list and the file is written with the banner — there is no early return for zero selected files.

### `run` — where it writes (the "only the draft path" guard)

- **should write exactly one file, at `draft_root/<repo>/.ai-factory/bootstrap-draft.md`, and nothing else anywhere under `draft_root`.** Setup: snapshot `set(draft_root.rglob("*"))` filtered to files after `run` and assert it equals the single expected path. The set-equality form is what makes this a guard rather than a smoke test.
- **should create the missing `<repo>/.ai-factory` parents when only `draft_root` exists.**
- **should leave the mirror worktree byte-identical when `run` completes.** Setup: snapshot `{path: path.read_bytes()}` before and after. Guards the load-bearing property that the draft never lands inside a git checkout of the repo, where it could be committed and then indexed.
- **should replace the previous draft in place, not append or duplicate, when `run` is called twice.** Fake distiller returns `"BODY-ONE"` then `"BODY-TWO"`; assert exactly one file, containing `"BODY-TWO"` once and `"BODY-ONE"` not at all.
- **should leave an already-reviewed, committed-style artifact untouched when `run` re-runs.** Pre-create `draft_root/<repo>/.ai-factory/ARCHITECTURE.md` and `draft_root/<repo>/docs/overview.md` with known bytes; run twice; assert both unchanged. This is spec 34's "no clobber, no re-poisoning" guard. Compare bytes, not mtimes — mtime resolution makes that flaky.
- **should keep per-repo drafts separate when two repos share one `draft_root`.**
- **should round-trip non-ASCII distiller output when reading the draft back as UTF-8.** The source passes `encoding="utf-8"` explicitly; this pins it against a regression to platform default encoding.
- **should return the path it actually wrote.**

### `_frame`

Call `_frame` directly (sync and pure) for the wording assertions; assert once via `run` that the written file is `_frame`'s output.

- **should preserve the distiller body verbatim and place it after the banner when framing arbitrary body text.** Assert `framed.endswith(body + "\n")`, `framed.count(body) == 1`, and `framed.index(body) > framed.index("Bootstrap draft")`. Bootstrap adds only the frame — no prompting, no rewriting of the distilled text.
- **should carry the LLM-generated/unreviewed marker with all three claims when framing any body:** machine-generated and not human-reviewed, NOT indexed into the knowledge store, and must never be committed as-is. Assert lowercase substring presence of `"machine-generated draft"`, `"not indexed into the knowledge store"`, `"never be committed as-is"`. Non-obvious: assert on these semantic fragments only — never on whole-document equality, which would go red on harmless wording edits and teach the next agent to delete the test.
- **should render the marker as a markdown blockquote so it survives rendering** — assert at least one line starts with `"> "` and that it precedes the body.
- **should still emit heading, banner and a trailing newline when the body is the empty string.**

### Logging (optional, low value)

- **should log the repo, ref, selected-file count and draft path on completion.** `caplog` at INFO. Include only if the operator-facing log line is treated as contract.

## Gotchas

- **Worktree lifetime vs. the returned `Path`.** `RepoMirror.tree` deliberately does *not* remove the worktree in `finally` — reclamation is deferred to the repo's next `ensure()` so already-yielded paths stay valid. The intuitive fake (delete the temp dir on context exit) models a contract the real class explicitly rejects, and would let a "reads after the `with`" regression pass. Fake the deferred behavior: keep the directory, flip a `tree_open` flag.
- **Transient worktree vs. durable draft location.** The draft is never written into the worktree. It goes to `draft_root/<repo>/.ai-factory/bootstrap-draft.md` under `settings.bootstrap_draft_root` (wired in `scripts/bootstrap.py`) — a durable location *outside* any git checkout. That placement is the second half of the guard: even if the path were selected, it isn't inside a repo anyone pushes, so `KnowledgeSync` never sees it. Tests must use `tmp_path` for `draft_root`; pointing it at the repo would both dirty the tree and destroy the property under test.
- **The marker text's role.** The banner is the only barrier between a machine draft and a human treating it as ground truth — spec 34's "one-time, human-reviewed" guard is enforced by prose, not code. Assert its three claims by substring so wording can evolve, but so that deleting "NOT indexed into the knowledge store" or "never be committed as-is" goes red.
- **The constructor guard is half a guard.** It checks `AiFactorySourceStrategy` only; the injected strategy (in production `CodeSourceStrategy`) is never asked about the draft path. The invariant test must cover both strategies explicitly — that gap is precisely where the silent failure would enter.
- **Import `_DRAFT_RELPATH`, never retype it.** A hardcoded literal in the test makes the invariant test self-referential and useless after a constant edit.
- **Stay off the layers below.** Selection rules belong to `tests/knowledge/test_code_source_strategy.py`; grouping/composition to `tests/knowledge/test_code_distiller_contract.py`.
- **`rglob("*")` walks `.git` too.** The `.git` filter is applied per path after the walk, so keep fake worktrees tiny; do not create a real `.git` directory with git itself.
- **`tests/knowledge/conftest.py` is Postgres-backed.** Requesting `store`/`pg_pool`/`make_chunk` would make these tests need a database for no reason. The new file should declare its own fakes locally.
