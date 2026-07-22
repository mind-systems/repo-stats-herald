# Code Review: 4.2.1 — Linked-change contract + resolve tests (red)

**Risk Level:** 🟢 Low

**Files reviewed (code changes only):**
- `src/episodic/linked_change.py` (new) — `LinkedChange` value object + stubbed `LinkedChangeResolver`
- `tests/episodic/conftest.py` (modified) — git-repo fixtures for the resolve contract tests
- `tests/episodic/test_linked_change_contract.py` (new) — 6 red tests

(Plan/plan-review/JSON artifacts are non-code and not reviewed for bugs.)

## What the task requires

A contract + red-test task: define `LinkedChange` and a `resolve(repo, before, after)` STUB that raises, then pin the resolution semantics with tests that are red **only because the logic is absent** — greenable unchanged by 4.2.2 (spec 11). No production parsing logic is in scope.

## Verification performed

- **Ran the new tests** (`uv run pytest tests/episodic/test_linked_change_contract.py`): all 6 fail with `NotImplementedError` raised at `src/episodic/linked_change.py:50`. Every test reaches `resolver.resolve(...)` and fails there — none error in a fixture, import, or git-plumbing step. This is the correct red state (spec 45's "green never before red" guard).
- **Full-suite collection** (`pytest --collect-only`): 38 tests collected, no import errors — the conftest additions (`GitCommitCollector`, `LinkedChangeResolver`, `AiFactorySourceStrategy` imports; new git fixtures) do not break the existing episodic-store or other suites.
- **Traced each test to greenability** under spec 11's identifier-keyed set-difference:
  - *genuine become-done:* after-done `{4.1.1, 4.2.1}` − before-done `{4.1.1}` = `{4.2.1}` ✓
  - *relocated already-done:* `4.1.1` is `[x]` in both versions (moved, re-indented, reworded, same `N.N.N` key) → cancels; `4.2.1` stays `[ ]` → `completed_tasks == ()` ✓ — the identifier key (not line text) is exactly what makes this greenable, matching the plan-review fix.
  - *source-strategy path:* roadmap only at `.ai-factory/ROADMAP.md`; a root-hardcoded resolver leaves it empty and fails — pins the concrete defect the spec names ✓
  - *commits-only fallback:* no roadmap in either commit; range yields ≥1 commit ✓
  - *merge / empty-range:* merge built with `--no-ff` and pinned identity; empty range via `sha..sha` — both only assert types, so no over-pinning ✓

## Correctness / security notes

- **Value object** matches spec 45 exactly (`repo`, `completed_tasks: tuple[str, ...]`, `commits: CommitContext`) and mirrors the codebase idiom (`@dataclass(frozen=True, slots=True)`, as in `src/commits/models.py`).
- **DI** is correct: `LinkedChangeResolver(collector, source_strategy)` takes public classes via constructor, wired with concretes only in the `resolver` fixture (the composition root here) — consistent with the architecture and spec 11's "assembled from the injected mirror + collector".
- **All imports resolve** against ground truth; constructor arg order is consistent between the stub and the fixture.
- **Fixtures are isolated** from the Postgres `pg_pool`/`store` fixtures — the git-only resolve tests need no database, and run fine as sync tests under `asyncio_mode = "auto"`.
- **`roadmap_history` snapshot handling** correctly unlinks a stale roadmap when a later snapshot drops it (so a `None` snapshot genuinely has no roadmap in the tree), and keeps `None` commits meaningfully non-empty via `src_marker.txt`.
- No security surface: `subprocess.run` uses fixed argv lists (no shell), only in test fixtures over throwaway `tmp_path` repos.

## Findings

None. The stub, the value object, and all six tests are correct, red for the right reason, and greenable unchanged by 4.2.2.

REVIEW_PASS
