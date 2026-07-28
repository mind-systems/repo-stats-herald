## Code Review — 4.2.2 Linked-change resolver (impl)

**Change reviewed:** `git diff HEAD` — modifications to `src/episodic/linked_change.py` and `src/knowledge/source_strategy.py` (plus the plan/plan-review artifacts, not code).
**Plan:** `.ai-factory/plans/24-4-2-2-linked-change-resolver-impl.md`
**Spec:** `.ai-factory/specs/11-linked-change-resolver.md`
**Risk Level:** 🟢 Low

### Method
Read both changed files in full (not just the hunks), the collector they reuse (`src/commits/collector.py`), the source-strategy ABC and its concrete, the six red tests (`tests/episodic/test_linked_change_contract.py`), and their fixtures (`tests/episodic/conftest.py`). Ran the two relevant suites:

```
uv run pytest tests/episodic/test_linked_change_contract.py tests/knowledge/test_source_strategy.py -q
→ 22 passed
```

All six 4.2.1 red tests are now green and the source-strategy suite is undisturbed by the `roadmap_paths` addition.

### Correctness — traced each contract case against the code
- **genuine become-done:** `before_done = {4.1.1}`; iterating `after`'s done lines yields `4.1.1` (in `before_done` → skipped) then `4.2.1` (fresh) ⇒ `("4.2.1",)`. ✓
- **relocated already-done:** the moved/re-indented/reworded `[x] 4.1.1` is in `before_done`; `4.2.1` in `after` is `[ ]` (not matched by `_DONE_LINE_RE`) ⇒ `()`. The false-positive trap is defeated because keying is by the `\d+(?:\.\d+)+` identifier, not line text. ✓
- **ai-factory path:** candidate `ROADMAP.md` absent at both refs → `_read_roadmap_at` returns `None` for both → loop advances to `.ai-factory/ROADMAP.md`, present → chosen ⇒ `4.2.1` captured. ✓
- **no-roadmap fallback:** both candidates `None`/`None` at both refs ⇒ `_read_roadmap_versions` returns `(None, None)` → `completed_tasks == ()`; `collect(repo, "before..after")` still returns the one `src_marker.txt` commit. ✓
- **merge range:** no roadmap in the fixture ⇒ `()`; `collect` tolerates the `--no-ff` merge range. ✓
- **empty range (`before == after`):** same content both sides ⇒ empty difference; `collect(repo, "sha..sha")` returns an empty `CommitContext` without error. ✓

### Runtime-failure checks
- **Guard "reads the mirror only":** `_read_roadmap_at` shells `git show --end-of-options <ref>:<path>` — local plumbing, no `fetch`/`pull`. `--end-of-options` matches the collector's own hygiene (`src/commits/collector.py:49`) so a ref starting with `-` cannot be parsed as an option. List-form `subprocess.run`, no `shell=True` → no shell-injection surface. ✓
- **Never-crash guard:** `check=False` + `returncode != 0 → None` folds "path absent at that ref" into the commits-only path; `before_content or ""` folds `None` and `""` together. A genuinely empty-but-present roadmap (`""`, returncode 0) is correctly treated as present (`"" is not None`), so the loop stops at that candidate rather than falling through — correct. ✓
- **No new commit-reading logic:** commits come from `GitCommitCollector.collect` verbatim, inheriting its empty-range/merge tolerance. ✓
- **Type/DI:** `roadmap_paths` is additive on the ABC with a `()` default, so no existing `SourceStrategy` subclass breaks; the `Iterator` return annotation and `re`/`subprocess` imports resolve at runtime (suite passes). `episodic` depends only on `commits/` and the injected `knowledge` `SourceStrategy` abstraction — no feature-internal import introduced. ✓
- **Determinism:** `completed_tasks` order is the `after` document's done-line order with a `seen` dedup — stable across runs. ✓

### Context Gates
- **Architecture / CLAUDE.md:** PASS. Git-read detail stays encapsulated in the resolver (mirrors "owned details stay inside the owning class"); concretes wired only at the conftest/composition root; regexes are module constants following `collector.py`'s style.
- **Rules (`.ai-factory/RULES.md`):** PASS — file intentionally empty.
- **Roadmap linkage:** PASS — `ROADMAP.md` line 51 (4.2.2) names spec `11-linked-change-resolver.md`; behavior + guards conform.
- **Docstring hygiene:** PASS — the stub's "this is a stub" wording is replaced with an accurate present-tense description; no plan/roadmap references leak into code comments.

### Critical Issues
None.

### Deferred observations (out of scope for 4.2.2 — noted for later hardening)
- **First-dotted-number heuristic vs. "leading identifier" wording.** `_TASK_ID_RE.search(line)` takes the *first* `\d+(?:\.\d+)+` anywhere on a done line. For every real and tested roadmap done line the task id leads the text (`- [x] **N.N.N — …**`), so this is exact in practice — and it correctly finds the id even when the description later contains a version-like token (e.g. `Python 3.12`), because the leading id is matched first. The only divergence from the spec's literal "leading `N.N.N`" is a hypothetical done checkbox with *no* leading id but a dotted number in its prose (e.g. `- [x] Bump to Python 3.12`), which would be mis-keyed as task `3.12`. No roadmap authored under this workflow produces such a line, and no test exercises it; flagging only so a future tightening (anchor the id to the checkbox prefix) is a conscious choice, not a regression. [dismissed]
- **Cross-path roadmap move within one range** (already raised in plan-review-1's deferred note): picking the first candidate present at *either* ref reads both versions from that single path, so a roadmap relocated root→`.ai-factory/` mid-range would miss completions. Outside this task's either/or path contract; no test covers it. [dismissed]

REVIEW_PASS
