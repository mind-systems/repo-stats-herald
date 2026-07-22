## Code Review Summary

**Files Reviewed:** 1 plan (`.ai-factory/plans/27-5-1-code-source-strategy.md`), checked against `src/knowledge/source_strategy.py`, `src/knowledge/indexer.py`, `src/knowledge/__init__.py`, `tests/knowledge/test_source_strategy.py`, spec `.ai-factory/specs/32-code-source-strategy.md`, concept `docs/concepts/source-strategy-profiles.md`, and ROADMAP line 5.1.
**Risk Level:** 🟢 Low

### Context Gates

- **Architecture (`.ai-factory/ARCHITECTURE.md`):** PASS. The plan adds a pure feature-internal class extending an existing ABC, no cross-feature imports, no concrete wiring — matches the feature-modular + DI + composition-root rules. The explicit "no composition-root wiring in this task" decision is architecturally correct: wiring both profiles belongs to 5.3+.
- **Rules (`.ai-factory/RULES.md`):** PASS. File is intentionally empty (no counter-defaults); nothing to enforce.
- **Roadmap (`.ai-factory/ROADMAP.md` line 59, task 5.1):** PASS. Plan title, target file, class name, guard (one concrete profile, not a registry), exclusion set (tests/vendored/generated), and complement-not-replace intent all match the contract line and the `Spec:` it names (`.ai-factory/specs/32-code-source-strategy.md`). Downstream consumers 5.3/5.4 are correctly identified.

### Ground-truth verification

Every "Notes for the implementer" assumption was checked against the actual files and holds:
- `SourceStrategy` ABC signature (`selects` abstract, `roadmap_paths` default `()`) — confirmed; the `AiFactorySourceStrategy` docstring does name `CodeSourceStrategy(SourceStrategy)` as the 5.1 extension.
- `ArtifactIndexer` consumes the strategy purely via `strategy.selects(path)`; a non-selected path is a logged no-op — confirmed (indexer.py:32-34).
- `src/knowledge/__init__.py` is empty; imports are module-direct — confirmed, so no export edit is needed.
- Existing test pattern (parametrized `SELECTED` / `NOT_SELECTED`, `is True/False`) — confirmed; the Task 2 mirror is faithful. `tests/knowledge/` already holds `conftest.py`, so the new file drops in cleanly.
- Not overriding `roadmap_paths()` for a code-only profile is consistent with the ABC's own docstring, which anticipates exactly this case.

The exclusion-first ordering and the segment-set (exact-match, not substring) design are sound: `src/latest/x.py` is not caught by the `test` segment, and `src/.venv/lib/x.py` is correctly excluded via the `.venv` segment. The generated-file globs correctly backstop `.d.ts` (basename `index.d.ts` matches `*.d.ts` even though its rightmost extension is `.ts`).

### Critical Issues

None.

### Minor Issues

**1. Extension-match guidance contradicts the pinned extension set (Task 1, plan lines 36 & 40).**
`_SOURCE_EXTENSIONS` is pinned **with leading dots** — `.py .ts .tsx …`. The extraction is pinned as "match on the basename's extension, e.g. via `path.rsplit(".", 1)`". But `"src/app/service.py".rsplit(".", 1)[-1]` is `"py"` (no dot), and `"py" in {".py", …}` is `False`. Taken literally, the two pinned mechanisms select **nothing** — every SELECTED case in Task 2 would fail on the first pass. The section's stated purpose is that "no value is guessed at implementation time," so this internal inconsistency should be reconciled in the plan rather than left for the implementer to discover via failing tests. Fix either side, e.g.:
- keep the dotted set and extract with `os.path.splitext(path)[1]` (returns `".py"`), which also avoids the `IndexError` on an extensionless basename like `cmd/tool/main` that `rsplit(".", 1)[1]` would raise; **or**
- keep `rsplit` and define the set dotless (`"py"`, `"ts"`, …).

The `splitext` form is preferable because it is dot-safe and crash-safe for extensionless paths under source roots.

### Positive Notes

- The plan does the ground-truth read the global rules demand: it walked `SourceStrategy` → `AiFactorySourceStrategy` → `indexer.py` → existing test → spec → concept, and pins the design against what it found rather than a description.
- Scope discipline is exemplary: the plugin registry, per-language config, auto-detection, and composition-root wiring are all explicitly deferred with citations to the spec Guards and the concept's non-goals — matching the "one concrete profile" contract exactly.
- The Tradeoxy-layout unknown is handled honestly: the assumption (`src/` leads `_SOURCE_ROOTS`) is recorded with a concrete fallback instruction, rather than silently guessed.
- Task 2's cases cover every spec Verification clause, including the independence/co-run assertion that exercises the "both profiles neither error nor conflict" requirement.

Aside from the extension-match wording, the plan is faithful to the spec, correctly scoped, and grounded in the actual code.
