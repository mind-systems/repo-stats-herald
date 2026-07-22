## Plan Review Summary

**Plan:** 5.2.2 — Code-to-feature distillation (impl)
**Files the plan touches:** `src/knowledge/code_distiller.py`, `scripts/eval.py`, `evals/cases.yaml` (+ user-authored `evals/reference/tradeoxy-features.md`)
**Risk Level:** 🟢 Low

### Context Gates

- **Governing spec (`.ai-factory/specs/33-code-to-feature-distillation.md`):** ✅ Aligned. The plan implements the per-unit read→prompt→compose flow, encodes the rubric verbatim from the concept doc, keeps the LLM seam model-agnostic, and reuses 5.2.1's grouping unchanged — matching every Change/Guard clause. The spec's `Files & types` lists only `code_distiller.py`, but the spec's own **Verification** clause mandates running through the eval harness against a Tradeoxy reference. The roadmap's eval-registry task (ROADMAP.md:18) resolves the tension explicitly: "each later producer registers its own handler as part of its verification wiring — no per-phase eval task." So Phase 2's edits to `scripts/eval.py`/`evals/cases.yaml` are the required verification wiring, not scope creep. The plan correctly fills the spec's under-listing. **WARN (non-blocking):** the spec's `Files & types` section is narrower than what its Verification demands — a spec inconsistency, not a plan defect.
- **ARCHITECTURE.md:** ✅ Aligned. Concretes (`OllamaClient`, `CodeSourceStrategy`, `CodeDistiller`) are wired only at the composition root (`scripts/eval.py::main`); `CodeDistiller` receives the `LLMClient` abstraction via constructor and never builds a concrete client; prompt templates live beside the owning class, mirroring `src/summarization/prompt.py`. Feature→infra dependency direction preserved.
- **RULES.md:** ✅ No applicable counter-defaults (file intentionally empty).
- **Roadmap linkage:** ✅ ROADMAP.md:61 (`5.2.2`) → spec 33 → concept doc `code-derived-understanding.md`. Chain intact.

### Critical Issues

None.

### Verified — assumptions confirmed against ground truth

- **Signature extension `distill(repo, paths) -> str` → `distill(repo, paths, tree: Path) -> str` is safe.** Grep confirms no caller of `.distill(` exists anywhere in `src`/`scripts`/`tests` — 5.3/5.4 are unbuilt (ROADMAP.md:62–63, both `[ ]`). The 5.2.1 contract test (`tests/knowledge/test_code_distiller_contract.py`) constructs `CodeDistiller(fake_llm)` and calls only `group_units`/`compose`, never `distill`, so it stays green regardless of the signature change. The 3-arg shape also reads *forward*-consistent with 5.3's "`CodeDistiller.distill` (5.2) over the mirror's HEAD" and mirrors `ArtifactIndexer.index(repo, path, tree)` exactly. This is a well-reasoned finalization of a pinned-but-unconsumed interface, documented in Design decision #1.
- **`(tree / path).read_text(encoding="utf-8")` + `UnicodeDecodeError`-only skip** matches `ArtifactIndexer.index` (indexer.py:37–39) precisely. Paths reach `distill` only after `strategy.selects` over an enumerated tree, so `FileNotFoundError` is not a realistic path — consistent with the indexer catching only `UnicodeDecodeError`.
- **Eval handler filtering** (`rglob("*")`, skip non-files / `.git` in parts, `relative_to(...).as_posix()`, `strategy.selects(rel)`) is byte-for-byte the shape of `KnowledgeSync.backfill` (sync.py:44–48). `CodeSourceStrategy.selects` operates on repo-relative posix paths — the currency produced. ✅
- **Composition-root wiring** uses `settings.ollama_url`, `settings.ollama_model`, `settings.ollama_api_key`, all present in `src/core/config.py` and already used identically for the `summary` handler in `main()`. ✅
- **Case inputs** — `_load_cases` folds every key except `name`/`type` into `inputs`, so `{repo, root}` reach the handler as `inputs["repo"]`/`inputs["root"]`. ✅
- **Determinism** — `rglob` order is unsorted, but `group_units` sorts units-by-module and paths-within-unit, so the composed output is stable across runs. ✅
- **Reference discipline** — `evals/reference/` holds only `.gitkeep`; the plan correctly instructs that `tradeoxy-features.md` is user-authored and never fabricated, and does not create it. The harness (`EvalRunner`) only writes outputs (no automated diff), so the "names features, not classes" acceptance is a manual review — matching the existing summarization eval discipline. ✅

### Positive Notes

- Design decision #1 is exemplary: it names the exact tension (pinned 2-arg shape vs. "read from the mirror"), grounds the resolution in the concrete precedent (`ArtifactIndexer.index`'s `tree` param), and proves no consumer breaks — the kind of reasoning that prevents a downstream reviewer from mistaking a justified deviation for a defect.
- The plan pins the rubric as *verbatim copy from `docs/concepts/code-derived-understanding.md`*, explicitly forbidding invented criteria — directly honoring the spec's "Rubric, not invention" guard, including the genre steer against both history/process phrasing and symbol/call-chain dumps.
- Task decomposition respects the red-test contract: Task 1 fills only `group_units`/`compose` bodies, leaving constructor and signatures untouched, so 5.2.1's five tests green without a model call.
- Empty-content and undecodable-file paths are handled explicitly (skip, debug-log, no empty LLM call), and transport/timeout errors are told to propagate per the `LLMClient` contract — no silent empty summaries.

### Minor observations (non-blocking, implementer will absorb naturally)

- Task 1 uses `os.path.dirname` and Task 3 adds `from pathlib import Path`; the module currently imports only `dataclass`/`LLMClient`. Adding `import os` (Task 1) and a module `logger = logging.getLogger(__name__)` / `import logging` (Task 3, since it says "debug-log the skip, matching `ArtifactIndexer.index`") are self-evident consequences of the referenced patterns — the indexer shows both — and need no separate plan step. Flagged only for completeness.

PLAN_REVIEW_PASS
