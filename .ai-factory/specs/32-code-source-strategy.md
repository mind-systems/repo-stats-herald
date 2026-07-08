# 5.1 — Code source strategy

**Phase:** 5 — Code-derived understanding. Depends on 3.4 (the `SourceStrategy` seam). First task; the profile that selects a code-only project's sources.

## Current state

The `SourceStrategy` seam (3.4) is first-class and swappable, but only the default ai-factory profile ships — it selects curated artifacts (`CLAUDE.md`, `ARCHITECTURE.md`, `ROADMAP.md`, `docs/**`) and leaves out code entirely. A code-only project (no such artifacts) selects nothing under that profile — it has no source at all.

## Change

Add a second, concrete `SourceStrategy` implementation that selects a project's source code, distinct from and complementary to the artifact profile.

- `src/knowledge/code_source_strategy.py` — `CodeSourceStrategy(SourceStrategy)`: `selects(path: str) -> bool` — matches the language's source roots (e.g. `src/**`, or the project's configured source root), excluding tests (`tests/**`, `*_test.*`, `test_*.*`), vendored/third-party dependencies, and generated files.
- A repo can run **both** profiles at once (the artifact profile for what it curates, the code profile for what it doesn't) — they are independent, composable selections, not mutually exclusive.

## Files & types

- new `src/knowledge/code_source_strategy.py` (`CodeSourceStrategy`)

## Guards

- **One concrete code profile, not a plugin registry** — per-language variation, generated-file detection heuristics, and a profile-selection mechanism are explicitly deferred (the plugin-registry direction in `source-strategy-profiles.md` stays a forward-looking concept, not built here).
- Complements the artifact profile — never replaces it; a harnessed repo keeps using the artifact profile unchanged.
- Excludes tests, vendored dependencies, and generated files — these are not "the project's features."

## Verification

- On a code-only repo (Tradeoxy), `CodeSourceStrategy.selects` returns the source files under its source root.
- A test file, a vendored dependency path, and a generated file are excluded.
- Running both profiles on a harnessed repo with some code selected by neither errors nor conflicts — each selects independently.
