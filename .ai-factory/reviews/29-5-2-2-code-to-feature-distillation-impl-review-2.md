# Code Review (round 2, re-review): 5.2.2 — Code-to-feature distillation (impl)

Re-reviewed after fixes. Ran `git diff HEAD` / `git status`. The only code change since round 1 is `evals/cases.yaml`; `src/knowledge/code_distiller.py` and `scripts/eval.py` are byte-identical to round 1.

## Verdicts on round-1 findings

### 1. [High] Configured Tradeoxy `root` selected zero files → **Fixed**

Current content of `evals/cases.yaml:14-25`:

```yaml
  # `root` points at a local checkout of the Tradeoxy monorepo's
  # tradeoxy_core sub-project — the code-only unit whose sources live under
  # a top-level src/, matching CodeSourceStrategy's root-anchored prefixes
  # (the monorepo root itself has no top-level src/ and carries its own
  # .ai-factory/, so it selects nothing). `make eval` writes
  # evals/out/tradeoxy-features.md; the comparison reference
  # evals/reference/tradeoxy-features.md is user-authored — never
  # fabricated by the implementer, same discipline as the summarization eval.
  - name: tradeoxy-features
    type: distill
    repo: tradeoxy-core
    root: /Users/max/projects/tradeoxy/tradeoxy_core
```

`root` now points at the `tradeoxy_core` sub-project, and `repo` is relabeled `tradeoxy-core`. Verified against ground truth by running the exact `DistillCaseHandler` selection logic over the new root:

```
root exists: True
selected: 240   (src/main.ts, src/app.service.ts, src/app-service.module.ts, …)
```

The handler now hands `distill` a non-empty `paths` list, so the eval produces real distilled output instead of an empty file. The added comment also correctly documents *why* the monorepo root was wrong (no top-level `src/`, carries its own `.ai-factory/`). Finding resolved.

## Full re-review for new issues

- **Contract tests still green** — `uv run pytest tests/knowledge/test_code_distiller_contract.py` → 5 passed. `group_units`/`compose`/constructor unchanged.
- **No new callers or signature drift** — `distill(repo, paths, tree)`'s only caller remains `scripts/eval.py`.
- **`code_distiller.py` and `scripts/eval.py` unchanged** — the correctness review from round 1 still holds: UTF-8-only skip matches `ArtifactIndexer.index`; `str.format` code substitution is injection-safe; DI/composition-root discipline intact; transport errors propagate.
- **`repo` label `tradeoxy-core` is cosmetic** — it flows only into `distill`'s `repo` arg, used solely in debug-log strings; no path or lookup depends on it. No issue.

No new findings.

REVIEW_PASS
