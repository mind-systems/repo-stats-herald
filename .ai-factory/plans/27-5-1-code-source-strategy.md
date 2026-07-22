# Plan: 5.1 — Code source strategy

## Context
Add a second concrete `SourceStrategy` profile that selects a code-only project's source files — the complement to the artifact profile, which selects nothing in a repo that has no ai-factory artifacts. Feeds the Phase 5 code-derivation path (bootstrap 5.3, episodic code-derivation 5.4).

## Settings
- Testing: yes
- Logging: none
- Docs: no

## Notes for the implementer

Ground truth read before planning:
- `src/knowledge/source_strategy.py` — `SourceStrategy` ABC: `selects(path: str) -> bool` (abstract) and `roadmap_paths() -> tuple[str, ...]` (default `()`). `AiFactorySourceStrategy` is the shipping default profile; its docstring already names `CodeSourceStrategy(SourceStrategy)` as the 5.1 extension.
- `src/knowledge/indexer.py` — `ArtifactIndexer` consumes a `SourceStrategy` purely via `strategy.selects(path)`; a non-selected path is a no-op. Nothing else in the seam is called on the strategy during indexing.
- `tests/knowledge/test_source_strategy.py` — the existing profile-test pattern: parametrized `SELECTED` / `NOT_SELECTED` path lists asserting `selects(...) is True/False`. Mirror this exactly.
- Spec `.ai-factory/specs/32-code-source-strategy.md` and concept `docs/concepts/source-strategy-profiles.md`.

Design decisions pinned so no value is guessed at implementation time:
- **`selects` is exclusion-first.** Check test / vendored / generated patterns first and return `False` on any match — even when the path also sits under a source root (e.g. `src/foo/foo.test.ts`, a vendored file under `src/`). Only then test source-root membership.
- **Source membership = recognized source-root prefix AND recognized source extension.** This honours the spec's "the language's source roots (e.g. `src/**`)" while keeping the profile a single hardcoded concrete strategy. Per-language config / auto-detection / a profile registry are explicitly deferred (spec Guards, and `source-strategy-profiles.md` §Non-goals) — do NOT introduce them.
- **`roadmap_paths()` is NOT overridden.** A code-only project has no roadmap concept, so it inherits the base default `()`. Do not add a roadmap-paths method.
- **No composition-root wiring in this task.** The spec's Files section lists only the new module. Wiring the code profile into a run (alongside the artifact profile) belongs to 5.3+; this task delivers the class and its tests only. `src/knowledge/__init__.py` is empty and imports are module-direct — no export edit needed.

Assumption recorded (Tradeoxy layout is not in this repo to inspect): the concrete source-root set below leads with `src/`, matching the spec's canonical `src/**` example and this org's NestJS/TS conventions. If the implementer can inspect the Tradeoxy mirror and its top-level source root differs, add that root to `_SOURCE_ROOTS` — the exclusion and extension logic is unaffected.

## Tasks

### Phase 1: Implement the code profile

- [x] **Task 1: Add `CodeSourceStrategy(SourceStrategy)`**
  Files: `src/knowledge/code_source_strategy.py`
  Create the module with a single class `CodeSourceStrategy(SourceStrategy)` importing the ABC from `src.knowledge.source_strategy`. Implement `selects(self, path: str) -> bool` as a pure function over the repo-relative path (no I/O, no logging), following the exclusion-first order pinned above. Give it a class docstring stating it is the one concrete code profile (complements, never replaces, the artifact profile; registry/per-language variation deferred). Define the matching sets as class constants:

  - `_SOURCE_ROOTS` (prefix tuple): `"src/"`, `"lib/"`, `"app/"`, `"internal/"`, `"pkg/"`, `"cmd/"`.
  - `_SOURCE_EXTENSIONS` (set): `.py .ts .tsx .js .jsx .go .rs .java .kt .rb .php .c .h .cpp .hpp .cs .swift .dart .scala .vue`.
  - `_EXCLUDED_DIRS` (segment set — any path segment matching excludes the path): tests → `tests`, `test`, `__tests__`; vendored → `node_modules`, `vendor`, `venv`, `.venv`, `third_party`, `bower_components`, `.yarn`; generated → `dist`, `build`, `out`, `target`, `.next`, `coverage`, `__pycache__`.
  - `_EXCLUDED_FILE_GLOBS` (fnmatch patterns against the basename): tests → `test_*.py`, `*_test.*`, `*.test.*`, `*.spec.*`, `*_spec.rb`; generated → `*.min.js`, `*.min.css`, `*.d.ts`, `*_pb2.py`, `*_pb2_grpc.py`, `*.pb.go`, `*.g.dart`, `*.generated.*`.

  Logic: split `path` on `/`; if any segment is in `_EXCLUDED_DIRS`, return `False`; if the basename matches any `_EXCLUDED_FILE_GLOBS` (use `fnmatch.fnmatch`), return `False`; otherwise return `path.startswith(_SOURCE_ROOTS) and os.path.splitext(path)[1] in _SOURCE_EXTENSIONS`. Use `os.path.splitext` for the extension — it returns the dotted suffix (`".py"`), matching the dotted `_SOURCE_EXTENSIONS` set, and yields `""` (not an `IndexError`) for an extensionless path like `cmd/tool/main`, which then correctly fails the membership test. Do not override `roadmap_paths()`.

### Phase 2: Verify selection

- [x] **Task 2: Selection tests for `CodeSourceStrategy`** (depends on Task 1)
  Files: `tests/knowledge/test_code_source_strategy.py`
  Mirror the structure of `tests/knowledge/test_source_strategy.py` (parametrized `SELECTED` / `NOT_SELECTED` lists). Cover the spec's Verification cases:
  - **Selected:** representative source files under a source root — e.g. `src/app/service.py`, `src/trading/order_book.ts`, `lib/exchange/client.go`, `app/models/user.rb`.
  - **Excluded — tests:** `tests/test_service.py`, `src/foo/foo.test.ts`, `src/foo/bar_test.go`, `src/service.spec.ts`.
  - **Excluded — vendored:** `node_modules/left-pad/index.js`, `vendor/github.com/x/y.go`, `src/.venv/lib/whatever.py`.
  - **Excluded — generated:** `dist/bundle.min.js`, `src/api/service_pb2.py`, `src/types/index.d.ts`, `build/main.js`.
  - **Excluded — non-source / artifact paths:** `CLAUDE.md`, `README.md`, `docs/spec/x.md`, `pyproject.toml` (proves the two profiles are independent — a path the artifact profile would take is not taken here).
  - **Independence / co-run:** one test asserting the two profiles select disjointly and without conflict — e.g. `CodeSourceStrategy().selects("src/app/service.py") is True` while `AiFactorySourceStrategy().selects("src/app/service.py") is False`, and the reverse for `.ai-factory/ROADMAP.md`. This exercises the spec's "running both profiles … neither errors nor conflicts" clause.
