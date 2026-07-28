# Test Plan: CodeBootstrap draft-path invariant

## Context
`src/knowledge/bootstrap.py` writes a machine-generated, unreviewed draft to a single fixed path (`_DRAFT_RELPATH`) whose whole safety rests on that path being one no source strategy selects — otherwise the next canonical push would auto-index the draft and poison memory with no error. These tests pin that invariant against *both* strategies (the constructor guard only checks the ai-factory one), plus the single-file write, no-clobber re-run, traversal/scoping, and the unreviewed marker.

## Settings
- Testing: yes
- Logging: minimal
- Docs: no

## Test Command
`uv run pytest tests/knowledge/test_bootstrap.py`

## Target Spec File
`tests/knowledge/test_bootstrap.py`

## Fixture Notes (apply across all tasks)
- Declare all fakes locally in this file. **Do NOT** use `tests/knowledge/conftest.py` fixtures (`pg_pool`, `store`, `make_chunk`) — they open a real Postgres pool; these tests must stay DB-free.
- **Import the constant, never retype it:** `from src.knowledge.bootstrap import _DRAFT_RELPATH`. A copied literal keeps the invariant test green after a constant edit — the exact silent failure this plan prevents.
- `FakeMirror` (duck-type of `RepoMirror`): `ensure(repo, org_id)` appends to `self.ensure_calls`; `tree(repo, org_id, ref)` is a `@contextlib.contextmanager` that records `(repo, org_id, ref)` in `self.tree_calls`, sets `self.tree_open = True`, yields a pre-populated `tmp_path` subdirectory, and in `finally` sets `self.tree_open = False` **without deleting the directory** (models the real deferred-reclamation contract).
- `FakeDistiller`: `async def distill(self, repo, paths, tree) -> str` — records `(repo, list(paths), tree)` and `tree_open_at_call` read off the mirror; returns canned bodies from a list so a second `run` can return a different body. Never subclass `CodeDistiller`.
- `strategy`: use the real `CodeSourceStrategy()` for end-to-end scoping; use a select-all `RecordingStrategy(SourceStrategy)` (returns `True` for everything, appends each argument) where traversal / `.git` filtering is the point.
- `draft_root`: always `tmp_path / "drafts"`; never the repo, never `settings.bootstrap_draft_root`.
- Async: `asyncio_mode = "auto"`, so `async def test_...` needs no marker.

## Tasks

### Phase 1: The write-guard invariant (`_DRAFT_RELPATH` × both strategies)

- [x] **Task 1: `_DRAFT_RELPATH` is outside every strategy's selected set**
  Files: `tests/knowledge/test_bootstrap.py`
  Test cases:
  - `should not be selected by either source strategy when _DRAFT_RELPATH is fed to CodeSourceStrategy().selects and AiFactorySourceStrategy().selects` — assert both return `False`, message naming the auto-index consequence; import `_DRAFT_RELPATH` from the module (do not retype it).
  - `should still be unselected by both strategies when the draft path carries its <repo>/ prefix` — feed `f"{repo}/{_DRAFT_RELPATH}"` to both strategies, both `False`.

- [x] **Task 2: constructor guard on the ai-factory-selected draft path**
  Files: `tests/knowledge/test_bootstrap.py`
  Test cases:
  - `should raise RuntimeError naming the draft path when _DRAFT_RELPATH is ai-factory-selected` — `monkeypatch.setattr("src.knowledge.bootstrap._DRAFT_RELPATH", ".ai-factory/specs/leak.md")` before constructing; assert `RuntimeError` whose message contains the offending path.
  - `should construct without raising when the real strategies are used` — guard happy path; a plain `CodeBootstrap(...)` with `CodeSourceStrategy()` constructs successfully.

### Phase 2: `__init__` — dependency surface

- [x] **Task 3: dependency surface excludes any knowledge store**
  Files: `tests/knowledge/test_bootstrap.py`
  Test cases:
  - `should expose exactly (mirror, distiller, strategy, draft_root) as constructor params` — `inspect.signature(CodeBootstrap.__init__).parameters` names equal the expected tuple (excluding `self`).
  - `should hold no knowledge-store dependency` — no stored attribute exposes a `query` / `upsert` / `delete_by_source` attribute (enforceable form of "never writes KnowledgeStore directly").

### Phase 3: `run` — traversal and scoping

Shared setup: a fake worktree under `tmp_path` containing `src/a/one.py`, `src/a/two.py`, `src/pkg/mod.ts`, `tests/test_x.py`, `node_modules/left-pad/index.js`, `dist/bundle.min.js`, `README.md`, `.git/config`, `.git/modules/src/nested.py`, plus at least one empty directory. Do not create a real `.git` with git itself — plain files/dirs.

- [x] **Task 4: strategy-selected posix paths passed to the distiller**
  Files: `tests/knowledge/test_bootstrap.py`
  Test cases:
  - `should pass only strategy-selected, repo-relative posix paths to the distiller when the worktree mixes source, test, vendored and generated files` — real `CodeSourceStrategy`; assert **set** equality of the paths the distiller received (not order).
  - `should distill with an empty path list and still write the draft when no worktree file is selected` — docs-only/empty repo; assert `distill` called with `[]` and the framed file is still written (no early return).

- [x] **Task 5: traversal never offers `.git`-internal paths or directories**
  Files: `tests/knowledge/test_bootstrap.py`
  Test cases:
  - `should never offer any .git-internal path to the strategy when the worktree contains .git/modules/src/nested.py` — use the select-all `RecordingStrategy`; assert no recorded path has a `.git` part.
  - `should never offer a directory to the strategy when the worktree contains empty and nested directories` — select-all `RecordingStrategy`; assert every recorded path corresponds to a file, not a directory.

- [x] **Task 6: mirror is ensured then distilled from HEAD, worktree open at call**
  Files: `tests/knowledge/test_bootstrap.py`
  Test cases:
  - `should ensure the mirror then open the tree at HEAD when run is called` — assert `mirror.ensure_calls == [(repo, org_id)]`, `mirror.tree_calls == [(repo, org_id, "HEAD")]`, and ensure was recorded before the tree open.
  - `should invoke the distiller while the worktree is still open` — assert `fake_distiller.tree_open_at_call is True` and the `tree` argument the distiller received is the yielded worktree path (guards against `distill` moving out of the `with` block).

### Phase 4: `run` — where it writes (the "only the draft path" guard)

- [x] **Task 7: exactly one file, at the draft path, nothing else**
  Files: `tests/knowledge/test_bootstrap.py`
  Test cases:
  - `should write exactly one file at draft_root/<repo>/.ai-factory/bootstrap-draft.md and nothing else under draft_root` — assert `set(draft_root.rglob("*"))` filtered to files equals the single expected path (set equality, not a smoke check).
  - `should create the missing <repo>/.ai-factory parents when only draft_root exists`.
  - `should return the path it actually wrote` — returned `Path` equals the expected draft path.

- [x] **Task 8: writes never touch the mirror worktree**
  Files: `tests/knowledge/test_bootstrap.py`
  Test cases:
  - `should leave the mirror worktree byte-identical when run completes` — snapshot `{path: path.read_bytes()}` for worktree files before and after `run`; assert unchanged (the draft never lands inside a git checkout).

- [x] **Task 9: idempotent re-run, no clobber of reviewed artifacts**
  Files: `tests/knowledge/test_bootstrap.py`
  Test cases:
  - `should replace the previous draft in place rather than append or duplicate when run twice` — distiller returns `"BODY-ONE"` then `"BODY-TWO"`; assert exactly one file containing `"BODY-TWO"` once and no `"BODY-ONE"`.
  - `should leave an already-reviewed committed-style artifact untouched when run re-runs` — pre-create `draft_root/<repo>/.ai-factory/ARCHITECTURE.md` and `draft_root/<repo>/docs/overview.md` with known bytes; run twice; assert both unchanged. Compare **bytes**, not mtimes.
  - `should keep per-repo drafts separate when two repos share one draft_root`.

- [x] **Task 10: encoding round-trip**
  Files: `tests/knowledge/test_bootstrap.py`
  Test cases:
  - `should round-trip non-ASCII distiller output when the draft is read back as UTF-8` — distiller returns non-ASCII body; read the file with `encoding="utf-8"` and assert the body survives (pins the explicit `encoding="utf-8"` write against a platform-default regression).

### Phase 5: `_frame` — the unreviewed marker

Call `_frame` directly (sync, pure) for wording assertions; assert once via `run` that the written file equals `_frame`'s output.

- [x] **Task 11: body preserved verbatim after the banner**
  Files: `tests/knowledge/test_bootstrap.py`
  Test cases:
  - `should preserve the distiller body verbatim and place it after the banner when framing arbitrary body text` — assert `framed.endswith(body + "\n")`, `framed.count(body) == 1`, and `framed.index(body) > framed.index("Bootstrap draft")`.
  - `should still emit heading, banner and a trailing newline when the body is the empty string`.

- [x] **Task 12: the marker carries all three unreviewed claims**
  Files: `tests/knowledge/test_bootstrap.py`
  Test cases:
  - `should carry the machine-generated / not-indexed / never-commit-as-is claims when framing any body` — assert lowercase-substring presence of `"machine-generated draft"`, `"not indexed into the knowledge store"`, and `"never be committed as-is"`. Assert on semantic fragments only — never whole-document equality.
  - `should render the marker as a markdown blockquote that precedes the body` — assert at least one line starts with `"> "` and that it appears before the body text.

### Phase 6: Logging (optional, low value — include only if the log line is treated as contract)

- [x] **Task 13: completion log line**
  Files: `tests/knowledge/test_bootstrap.py`
  Test cases:
  - `should log the repo, ref, selected-file count and draft path on completion` — `caplog` at INFO; assert the record carries repo, `"HEAD"`, the selected-file count, and the draft path.

## Out of Scope (do not re-test here)
- `CodeSourceStrategy` per-path selection rules — `tests/knowledge/test_code_source_strategy.py`.
- `group_units` grouping / `compose` composition — `tests/knowledge/test_code_distiller_contract.py`.
- Any Postgres / git / LLM integration — these tests are fully faked and DB-free.
