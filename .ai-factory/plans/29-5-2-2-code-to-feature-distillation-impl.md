# Plan: 5.2.2 — Code-to-feature distillation (impl)

## Context
Turn `CodeDistiller`'s stubs into real per-unit distillation: green 5.2.1's grouping/composition tests and add the real LLM prompting that reads each bounded unit's code from the mirror and produces delivered-behaviour feature descriptions — never a class/method/call-chain dump — via the model-agnostic `LLMClient`. Verified end-to-end through the eval harness against a user-authored Tradeoxy reference.

## Settings
- Testing: no
- Logging: minimal
- Docs: no

## Design decisions (read before implementing)

- **Reading from the mirror requires the tree.** 5.2.1 pinned `distill(repo, paths) -> str`, but distillation must "read each bounded unit's code from the mirror" and the pinned 2-arg shape carries no filesystem root. Resolve this by extending `distill` with the mirror tree exactly as `ArtifactIndexer.index(repo, path, tree)` already does: `distill(repo: str, paths: list[str], tree: Path) -> str`. This keeps `paths` as **repo-relative** paths — the currency `CodeSourceStrategy.selects` already speaks (`src/knowledge/code_source_strategy.py`) — and files are read via `(tree / path).read_text(...)`, identical to the indexer. This is an additive finalization of the interface that 5.3/5.4 (not yet built) will consume; both already open a worktree via `RepoMirror.tree(...)` (`src/github/mirror.py`), so they can hand the tree straight in.
- **5.2.1's tests stay green regardless.** `tests/knowledge/test_code_distiller_contract.py` constructs `CodeDistiller(fake_llm)` and only exercises `group_units`/`compose` — it never calls `distill`. Do **not** change the constructor (`__init__(self, llm)`) and do **not** change `group_units`/`compose`'s signatures or semantics; only fill in their bodies.
- **Rubric is verbatim, not invented.** The prompt encodes the distillation rubric from `docs/concepts/code-derived-understanding.md` § "What counts as a feature — the distillation rubric". The implementation copies those criteria; it authors none of its own.

## Tasks

### Phase 1: Core distillation (`src/knowledge/code_distiller.py`)

- [x] **Task 1: Implement the pure grouping/composition helpers**
  Files: `src/knowledge/code_distiller.py`
  Fill in `group_units` and `compose` exactly to the docstrings already in the stub (these green 5.2.1's tests, unchanged):
  - `group_units(paths)`: a path's module is `os.path.dirname(path)` (repo-root file → `""`); partition all paths into one `CodeUnit` per distinct module. Units sorted by `module` ascending; each unit's `paths` sorted ascending; the result is the full, disjoint partition (every input path in exactly one unit, none dropped or duplicated).
  - `compose(unit_texts)`: `"\n\n".join(unit_texts)` — deterministic, byte-identical for the same input order.
  Verify against `tests/knowledge/test_code_distiller_contract.py` (`uv run pytest tests/knowledge/test_code_distiller_contract.py`) — all five tests must pass without any real model call.

- [x] **Task 2: Add the feature-distillation prompt**
  Files: `src/knowledge/code_distiller.py`
  Add module-level template constant(s) and a private `_build_prompt(unit: CodeUnit, code: str) -> str` on `CodeDistiller`, mirroring the owned-prompt pattern in `src/summarization/prompt.py` (templates live beside the class that owns them; scope is this file only per the spec's Files & types). The prompt encodes the rubric verbatim from `docs/concepts/code-derived-understanding.md`:
  - **Discriminator:** a feature = a verifiable interaction a new e2e test could cover (user→system, system→system, system→external, or an internal subsystem with its own behaviour contract); refactors/cleanups/plumbing are internal and stay out.
  - **Naming:** 2–5 words from the operator's perspective — what the system can do; module/directory names never become feature names; prefer fewer, larger cross-cutting features over one-per-module.
  - **Genre:** present-tense delivered behaviour — state what the project does, never how it came to be. Explicitly steer against history/process phrasing ("was added", "was replaced", "previously", "this milestone") **and** against symbol/mechanism dumps ("class X has methods Y, Z" / call-chain listings).
  The prompt embeds the unit's concatenated code (per-file, path-headed) as the material to distill.

- [x] **Task 3: Implement `distill` — per-unit prompting over the mirror tree** (depends on Task 1, Task 2)
  Files: `src/knowledge/code_distiller.py`
  Change the signature to `async def distill(self, repo: str, paths: list[str], tree: Path) -> str` (add `from pathlib import Path`) and update its docstring to name the `tree` parameter. Flow:
  1. `units = self.group_units(paths)`.
  2. For each unit in order: read each of the unit's paths from the tree via `(tree / path).read_text(encoding="utf-8")`, skipping any path that raises `UnicodeDecodeError` (debug-log the skip, matching `ArtifactIndexer.index`). Concatenate the readable files into one code blob with a per-file path header.
  3. If a unit has no readable content, skip it (no empty prompt, no LLM call — debug-log).
  4. Otherwise `prompt = self._build_prompt(unit, code)` then `desc = await self._llm.generate(prompt)`; collect `desc` per unit, in unit order.
  5. Return `self.compose(unit_texts)`.
  Guards: never construct a concrete client — use the injected `self._llm`; let transport/timeout errors from `generate` propagate (never swallow into an empty description — per `LLMClient` contract); introduce no new grouping/composition behaviour beyond Task 1.

### Phase 2: Eval-harness verification path (`scripts/eval.py`, `evals/`)

- [x] **Task 4: Add and register a `distill` case handler** (depends on Task 3)
  Files: `scripts/eval.py`
  Add `DistillCaseHandler(CaseHandler)` alongside `SummaryCaseHandler`, following the same pattern (own no filename logic; drive the production producer). It is constructed with a `CodeDistiller` and a `CodeSourceStrategy`. In `run(inputs)`:
  - resolve a local checkout root from `inputs["root"]` as a `Path` (offline eval reads a local tree, exactly as the `summary` handler reads local git via `repo: "."`);
  - enumerate `root.rglob("*")`, skip non-files and anything with `.git` in its parts, compute the repo-relative posix path, and keep those where `strategy.selects(rel)` is true (same filtering shape as `KnowledgeSync.backfill`);
  - `return await self._distiller.distill(inputs["repo"], selected, root)`.
  In `main()`, wire the concretes at the composition root: `CodeDistiller(OllamaClient(settings.ollama_url, settings.ollama_model, settings.ollama_api_key))` and `CodeSourceStrategy()`, and register `handlers["distill"] = DistillCaseHandler(...)`. Leave the existing `summary` handler untouched.

- [x] **Task 5: Add the Tradeoxy distill case** (depends on Task 4)
  Files: `evals/cases.yaml`
  Add a `distill` case for Tradeoxy — `{name: tradeoxy-features, type: distill, repo: tradeoxy, root: <local Tradeoxy checkout path>}`. Note in a YAML comment that `root` points at a local Tradeoxy checkout the operator supplies, and that the comparison reference `evals/reference/tradeoxy-features.md` is **user-authored** (never fabricated by the implementer — same discipline as the summarization eval). `make eval` writes `evals/out/tradeoxy-features.md` for diffing against that reference; the acceptance check is that the output **names features, not classes**.
