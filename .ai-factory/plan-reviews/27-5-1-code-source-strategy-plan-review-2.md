## Code Review Summary

**Files Reviewed:** 1 plan (`.ai-factory/plans/27-5-1-code-source-strategy.md`), checked against `src/knowledge/source_strategy.py`, `src/knowledge/indexer.py`, `src/knowledge/__init__.py`, `tests/knowledge/test_source_strategy.py`, spec `.ai-factory/specs/32-code-source-strategy.md`, concept `docs/concepts/source-strategy-profiles.md`, and ROADMAP line 5.1.
**Risk Level:** 🟢 Low

### Context Gates

- **Architecture (`.ai-factory/ARCHITECTURE.md`):** PASS. The plan adds a single pure feature-internal class extending an existing ABC (`SourceStrategy`), with no cross-feature imports, no concrete-client construction, and no composition-root wiring — matching the feature-modular + constructor-DI + composition-root-only-wiring rules. The explicit "no composition-root wiring in this task" decision is architecturally correct: wiring both profiles into a run belongs to 5.3+.
- **Rules (`.ai-factory/RULES.md`):** PASS. File is intentionally empty (its own note states this is the correct result, not a gap); nothing to enforce.
- **Roadmap (`.ai-factory/ROADMAP.md` line 59, task 5.1):** PASS. Plan title, target file (`src/knowledge/code_source_strategy.py`), class name (`CodeSourceStrategy(SourceStrategy)`), the "one concrete profile, not a plugin registry" guard, the tests/vendored/generated exclusion set, and the complement-not-replace intent all match the contract line and its named `Spec:` (`.ai-factory/specs/32-code-source-strategy.md`). Downstream consumers 5.3/5.4 are correctly identified. The named spec and its referenced concept (`docs/concepts/source-strategy-profiles.md` §Non-goals) were walked to leaf — the deferral of registry/auto-detection/per-language config is faithful to both.

### Round-1 follow-up

The single minor issue raised in plan-review-1 — the extension-extraction mechanism (`rsplit(".", 1)` yielding a dotless `"py"`) contradicting the dotted `_SOURCE_EXTENSIONS` set and therefore selecting nothing — has been **resolved**. Line 40 now pins `os.path.splitext(path)[1]` (returns `".py"`), which matches the dotted set and is crash-safe on an extensionless path under a source root (`cmd/tool/main` → `""`, which correctly fails membership rather than raising). The plan even documents this rationale inline. No residual inconsistency remains.

### Ground-truth verification

Every "Notes for the implementer" assumption was re-checked against the actual files and holds:
- `SourceStrategy` ABC signature — `selects` abstract, `roadmap_paths()` default `()` — confirmed; the `AiFactorySourceStrategy` docstring does name `CodeSourceStrategy(SourceStrategy)` as the 5.1 extension.
- `ArtifactIndexer` consumes the strategy purely via `strategy.selects(path)`; a non-selected path is a logged no-op — confirmed (indexer.py:32–34). Nothing else on the strategy is called during indexing, so a code profile that overrides only `selects` is a complete, drop-in seam implementation.
- `src/knowledge/__init__.py` is empty; imports are module-direct — confirmed, so no export edit is needed.
- Existing test pattern (parametrized `SELECTED`/`NOT_SELECTED`, `is True/False`) — confirmed; the Task 2 mirror is faithful. `tests/knowledge/` already holds `__init__.py` and `conftest.py`, so the new file drops in cleanly.
- Not overriding `roadmap_paths()` for a code-only profile is consistent with the ABC docstring, which anticipates exactly this case ("A profile with no roadmap concept … returns `()`").

I traced every Task 2 case through the pinned exclusion-first logic (`str.startswith` accepts the prefix tuple; `_EXCLUDED_DIRS` is exact-segment, not substring; `fnmatch` against the basename), and all resolve as asserted:
- Selected sources (`src/app/service.py`, `lib/exchange/client.go`, `app/models/user.rb`) → `True`.
- Test exclusions caught by segment (`tests/…`) or basename glob (`*.test.*`, `*_test.*`, `*.spec.*`).
- Vendored exclusions caught by segment, including `src/.venv/lib/whatever.py` via the `.venv` segment.
- Generated exclusions caught by segment (`dist`, `build`) or glob (`*_pb2.py`, `*.d.ts` on basename `index.d.ts` even though its rightmost extension is `.ts`).
- Non-source/artifact paths (`CLAUDE.md`, `docs/spec/x.md`, `pyproject.toml`) fail source-root membership → `False`.
- The independence/co-run assertion (`src/app/service.py` selected by Code but not AiFactory; `.ai-factory/ROADMAP.md` the reverse) exercises the spec's "both profiles neither error nor conflict" clause.

No false-positive risk in the globs was found (`*_test.*` does not match `contest.go`; `*.test.*` does not match `latest.ts`).

### Critical Issues

None.

### Positive Notes

- The plan does the ground-truth read the global rules demand: it walked `SourceStrategy` → `AiFactorySourceStrategy` → `indexer.py` → existing test → spec → concept, pinning the design against what it found.
- Scope discipline is exemplary: plugin registry, per-language config, auto-detection, and composition-root wiring are all explicitly deferred with citations to the spec Guards and the concept's §Non-goals — matching the "one concrete profile" contract exactly.
- The Tradeoxy-layout unknown is handled honestly: the `src/`-leads-`_SOURCE_ROOTS` assumption is recorded with a concrete fallback instruction rather than silently guessed.
- Every value the implementer would otherwise guess is pinned: full source-root, extension, excluded-dir, and excluded-glob sets, plus the exact evaluation order and the extension-extraction call.

The plan is faithful to the spec, correctly scoped, grounded in the actual code, and the sole prior finding is fixed.

PLAN_REVIEW_PASS
