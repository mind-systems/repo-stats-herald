## Code Review Summary

**Change under review:** 5.1 — Code source strategy. Two new source files:
- `src/knowledge/code_source_strategy.py` — `CodeSourceStrategy(SourceStrategy)`
- `tests/knowledge/test_code_source_strategy.py`

(The other staged files are the plan, its two plan-reviews, and the planner JSON sidecar — artifacts, not code.)

**Risk Level:** 🟢 Low — a single pure, side-effect-free `selects(path) -> bool` implementation of an existing ABC. No I/O, no state, no wiring, no schema/migration, no concurrency, no network, no untrusted input. Nothing to break at runtime.

### Verification run

`uv run python -m pytest tests/knowledge/test_code_source_strategy.py` → **20 passed**. The full parametrized SELECTED/NOT_SELECTED matrix and the disjoint-co-run assertion all green.

### Ground-truth checks

- **ABC conformance.** `CodeSourceStrategy` implements the one abstract method `selects`; it correctly does **not** override `roadmap_paths()`, inheriting the base default `()` — exactly what the ABC docstring anticipates for a code-only profile with no roadmap concept. `ArtifactIndexer` consults the strategy only via `strategy.selects(path)` (indexer.py:32), so this is a complete, drop-in seam implementation.
- **Return type.** Every path returns a genuine `bool`: the two guard branches `return False` literally; the final `path.startswith(tuple) and <ext> in set` is `bool and bool`. The tests' `is True` / `is False` identity assertions therefore hold — no truthy-but-not-`True` leakage.
- **Exclusion-first ordering** is implemented as pinned: excluded-dir segment check → excluded-file glob check → source-root+extension membership. A test/vendored/generated path under a source root (`src/foo/foo.test.ts`, `src/.venv/lib/whatever.py`) is correctly rejected before the source-root gate can accept it.
- **Segment match is exact, not substring.** `_EXCLUDED_DIRS` membership is `segment in set`, so `src/latest/x.py` (segment `latest` ≠ `test`) and `contest`-style names are not falsely excluded.
- **Glob false-positive scan.** `*_test.*` requires a literal `_test.` (so `order_book.ts`, `latest.ts`, `manifest.ts` are safe); `*.test.*` requires `.test.` (so `contest.py` is safe); `*.d.ts` correctly catches `index.d.ts` on the basename even though its rightmost extension is `.ts`; `*_pb2.py` catches `service_pb2.py`. No unintended matches found among plausible source names.
- **Extension extraction** uses `os.path.splitext(path)[1]` against the dotted `_SOURCE_EXTENSIONS` set — consistent (the plan-review-1 mismatch is resolved), and crash-safe on an extensionless path under a source root (`cmd/tool/main` → `""` → not a member → `False`, no `IndexError`).
- **Imports** `os` and `fnmatch` are both used; no dead imports. No cross-feature imports — depends only on `src.knowledge.source_strategy`.

### Scope / correctness notes (non-blocking)

- The source-root gate assumes the project keeps code under one of `src/ lib/ app/ internal/ pkg/ cmd/`. The spec's real-repo verification ("Tradeoxy selects its sources") cannot be exercised in this repo — the Tradeoxy mirror is not present — and is legitimately deferred to the 5.3/5.4 wiring, where the strategy runs against an actual mirror. The plan records the `src/`-leads assumption with a concrete fallback (add Tradeoxy's root to `_SOURCE_ROOTS`), so this is a documented heuristic boundary, not a defect in this change.
- Extension/dir matching is case-sensitive and the exclusion sets are a fixed heuristic — both consistent with the "one concrete profile, per-language variation deferred" guard. No over-reach into a registry/config, matching the contract.

### Critical Issues

None.

### Minor Issues

None.

REVIEW_PASS
