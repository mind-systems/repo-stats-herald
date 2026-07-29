## Plan Review Summary

**Plan Reviewed:** `.ai-factory/plans/66-codebootstrap-draft-path-invariant.md`
**Type:** Test-authoring plan (red/characterization tests for `src/knowledge/bootstrap.py`)
**Risk Level:** 🟢 Low

### Context Gates
- **Roadmap (ROADMAP.md 5.3 — Semantic bootstrap):** ALIGNED. The plan pins exactly the 5.3 guard — "bootstrap writes ONLY the non-selected draft path — NEVER a source-selected path and NEVER the committed artifact … no direct `KnowledgeStore` write," refreshing the draft without clobbering reviewed work. Task 1 (both strategies), Task 3 (no store dependency), Task 7/8 (single draft path, worktree untouched), Task 9 (idempotent no-clobber) map one-to-one onto the guard.
- **Governing spec (`.ai-factory/specs/75-code-bootstrap-test-plan.md`):** ALIGNED. The plan is a faithful, near-verbatim realization of the spec's test-case catalogue, fixture contracts (`FakeMirror`/`FakeDistiller`/`RecordingStrategy`), and gotchas (deferred worktree reclamation, constant-import discipline, DB-free fakes, half-a-guard constructor note).
- **Architecture (`ARCHITECTURE.md`) / Rules:** No new production surface, DI, or module boundaries introduced — tests only. No violations.

### Critical Issues
None. Every assumption the plan makes about the target code was verified against ground truth:

- **Constant & path:** `_DRAFT_RELPATH = ".ai-factory/bootstrap-draft.md"` exists at module level in `src/knowledge/bootstrap.py:13`; write target is `draft_root / repo / _DRAFT_RELPATH` (`bootstrap.py:71`). Task 7's expected path is correct.
- **Strategy invariant (Task 1):** Confirmed by hand against both concretes. `CodeSourceStrategy.selects(".ai-factory/bootstrap-draft.md")` → `False` (not under a source root); `AiFactorySourceStrategy.selects(...)` → `False` (not in its literal sets, not under `.ai-factory/specs/` or `docs/`). The `<repo>/`-prefixed variant is also `False` for both. The plan correctly notes the constructor guard covers only the ai-factory half (`bootstrap.py:39`), so the static both-strategies test is the right place to pin the code half.
- **Constructor guard (Task 2):** `__init__` reads the module global `_DRAFT_RELPATH` at call time, so `monkeypatch.setattr("src.knowledge.bootstrap._DRAFT_RELPATH", ".ai-factory/specs/leak.md")` before construction will flip `AiFactorySourceStrategy().selects(...)` to `True` and raise `RuntimeError` naming the path (`bootstrap.py:39-43`). Correct.
- **Constructor surface (Task 3):** Signature is exactly `(mirror, distiller, strategy, draft_root)` (`bootstrap.py:32-38`); stored attrs are `_mirror/_distiller/_strategy/_draft_root`. Correct.
- **Traversal/scoping (Tasks 4–6):** `run` does `ensure` → `tree(repo, org_id, "HEAD")` → `rglob("*")` with `if not path.is_file() or ".git" in path.parts: continue`, feeding `relative_to(tree).as_posix()` to `strategy.selects`, then `distill(repo, selected, tree)` inside the `with` block (`bootstrap.py:55-67`). All Task 4/5/6 assertions (set-equality of selected paths, no `.git` path offered, no directory offered, ensure-before-tree ordering, distiller called with worktree open) match the code exactly.
- **Fake signatures:** `RepoMirror.ensure(repo, org_id)` and `@contextmanager tree(repo, org_id, ref)` (`mirror.py:108,133`) and `CodeDistiller.distill(self, repo, paths, tree)` (`code_distiller.py:69`) match the duck-typed fakes. The deferred-reclamation contract the fixture models is the real one (`mirror.py:159-163`).
- **Write behavior (Tasks 7–10):** `mkdir(parents=True, exist_ok=True)` then `write_text(framed, encoding="utf-8")` (`bootstrap.py:72-73`) supports the missing-parents, idempotent-overwrite, no-clobber, per-repo-separation, and UTF-8 round-trip cases. There is no early return for zero selected files, so Task 4's empty-list case holds.
- **Framing (Tasks 11–12):** `_frame` (`bootstrap.py:84-102`) emits heading `# Bootstrap draft …`, blockquote (`> `) banner lines, and `f"{body}\n"` last. All substring claims verified lowercase against the actual banner text: `"machine-generated draft"`, `"not indexed into the knowledge store"`, `"never be committed as-is"` are each present; `framed.endswith(body + "\n")` and `index(body) > index("Bootstrap draft")` hold.
- **Environment:** `asyncio_mode = "auto"` confirmed in `pyproject.toml`; `settings.bootstrap_draft_root` exists (`src/core/config.py:36`, default `"bootstrap-drafts"`), and the plan correctly forbids using it in favor of `tmp_path/"drafts"`. `tests/knowledge/conftest.py` is Postgres-backed (`pg_pool`/`store`/`make_chunk`), so the plan's instruction to declare local fakes and avoid those fixtures is correct. No `tests/knowledge/test_bootstrap.py` exists yet — this is a clean new file.

### Positive Notes
- **Constant-import discipline is the load-bearing decision and the plan states it repeatedly and correctly** — importing `_DRAFT_RELPATH` rather than retyping it is exactly what keeps the invariant test meaningful after a constant edit; a copied literal would be the silent failure the whole plan exists to catch.
- **Correct fake fidelity to the deferred-reclamation contract** — modeling `tree` as "flip a flag, do not delete on exit" avoids a fake that would green-light a real "reads-after-`with`" regression. This is the subtle trap and the plan names it.
- **Clean layer discipline** — selection rules and grouping/composition are explicitly declared out of scope and delegated to their existing test files, avoiding duplicate/brittle coverage.
- **Set-equality (not smoke) assertions** for both the selected-path set and the files-under-draft_root set turn these into real guards.

## Deferred observations
- Affects: `.ai-factory/specs/75-code-bootstrap-test-plan.md` (and Task 3, which mirrors it) — The "no knowledge-store dependency" sentinel list is `query` / `upsert` / `delete_by_source`, but the actual `KnowledgeStore` ABC (`src/knowledge/store.py`) exposes `upsert`, `delete`, and `query` — there is no `delete_by_source`. The mismatch is harmless in practice (any real store threaded in would still be caught by the `upsert`/`query` probes, so detection is not weakened), but the third sentinel checks for a method that does not exist. If this catalogue is revisited upstream, replacing `delete_by_source` with the real `delete` would make the sentinel set an exact mirror of the ABC. Non-blocking; the plan is correct to follow its governing spec verbatim. [fixed]

PLAN_REVIEW_PASS
