# Code Review: 5.2.2 — Code-to-feature distillation (impl)

Scope reviewed: `git diff HEAD` — `src/knowledge/code_distiller.py`, `scripts/eval.py`, `evals/cases.yaml` (plan/artifact files ignored). Read each changed file in full plus the collaborators they touch (`code_source_strategy.py`, `indexer.py`, `sync.py`, `config.py`, the 5.2.1 contract test).

## Findings

### 1. [High] The configured Tradeoxy `root` selects zero files — the eval silently produces empty output, defeating the spec's verification

`evals/cases.yaml` sets the new `distill` case to:

```yaml
  - name: tradeoxy-features
    type: distill
    repo: tradeoxy
    root: /Users/max/projects/tradeoxy
```

`DistillCaseHandler.run` enumerates `root.rglob("*")` and keeps paths where `CodeSourceStrategy.selects(rel)` is true. But `CodeSourceStrategy.selects` anchors its source-root prefixes at the repo root:

```python
return (
    path.startswith(self._SOURCE_ROOTS)   # ("src/", "lib/", "app/", "internal/", "pkg/", "cmd/")
    and os.path.splitext(path)[1] in self._SOURCE_EXTENSIONS
)
```

`/Users/max/projects/tradeoxy` is a **monorepo root** with no top-level `src/` — its sources live under sub-project dirs (`tradeoxy_core/src/…`, `tradeoxy_broker/…`, `tradeoxy_gui/…`). A relative path like `tradeoxy_core/src/streaming/foo.ts` does **not** start with any of the anchored prefixes, so nothing is selected.

Verified against ground truth (ran the exact handler selection logic):

```
selected from monorepo root (/Users/max/projects/tradeoxy):        0
selected from a sub-project (/Users/max/projects/tradeoxy/tradeoxy_core): 239  (src/main.ts, src/app.service.ts, …)
```

Failure scenario: `make eval` runs the case, `distill` is handed an empty `paths` list → `group_units([]) → []` → no LLM call → `compose([]) → ""` → `evals/out/tradeoxy-features.md` is written **empty**, with no error. The entire point of task 5.2.2's Verification clause ("distill Tradeoxy's features … names features, not classes") silently evaluates to nothing. This is exactly the silent-degradation class the phase exists to guard against.

Compounding it: `/Users/max/projects/tradeoxy` is not even a code-only project — it carries its own `.ai-factory/` and `CLAUDE.md` (it is the coordination-root monorepo). The distiller's unit is a single repo; the `root` must point at one code-only sub-project.

Fix: point `root` at a code-only sub-project whose layout matches `CodeSourceStrategy`'s root-anchored prefixes, e.g. `/Users/max/projects/tradeoxy/tradeoxy_core` (239 files selected, sources under `src/`). Confirm the operator authors `evals/reference/tradeoxy-features.md` for whichever sub-project is chosen.

## Verified correct (no action)

- **5.2.1 contract tests stay green.** `uv run pytest tests/knowledge/test_code_distiller_contract.py` → 5 passed. Constructor and `group_units`/`compose` signatures/semantics unchanged; `group_units` uses `os.path.dirname` which matches the tests' `rsplit("/",1)[0] if "/" in path else ""` expectation for both nested and repo-root paths.
- **Signature extension is safe.** `distill(repo, paths, tree)` — grep confirms the only caller anywhere is the new eval handler (`scripts/eval.py:92`); 5.3/5.4 are unbuilt. Mirrors `ArtifactIndexer.index(repo, path, tree)`.
- **UTF-8 handling** matches `ArtifactIndexer.index`: only `UnicodeDecodeError` is caught/skipped; paths reach `distill` from an enumerated tree so non-existence isn't a realistic path.
- **Prompt string safety.** `_PROMPT_TEMPLATE.format(code=…)` — code content is a substituted argument value, so literal `{`/`}` inside source files are not re-interpreted by `str.format`. No format-injection.
- **Determinism** — `rglob` order is irrelevant; `group_units` sorts modules and intra-unit paths, `compose` preserves order.
- **Composition-root/DI discipline** — `CodeDistiller` receives the `LLMClient` abstraction; concretes (`OllamaClient`, `CodeSourceStrategy`) wired only in `main()`. Transport/timeout errors from `generate` propagate (no silent empty summary).

## Minor observations (non-blocking)

- `main()` constructs a second `OllamaClient` for the distiller rather than sharing the summarizer's instance — harmless duplication, consistent with per-producer wiring.
- `root.rglob("*")` walks excluded trees (e.g. `node_modules`) before `selects` filters them, a potential slowness on a large JS/TS checkout — but this mirrors `KnowledgeSync.backfill`'s existing pattern, so it is consistent, not a regression.
