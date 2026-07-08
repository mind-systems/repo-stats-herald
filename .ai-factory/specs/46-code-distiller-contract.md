# 5.2.1 — Code distiller contract + grouping tests (red)

**Phase:** 5 — Code-derived understanding. Depends on 5.1 (the code source strategy), Phase 1 (`LLMClient`), Phase 3 (the mirror). First half of the distiller milestone — the signature + bounded-unit mechanics, pinned with red tests, ahead of the real distillation implementation (5.2.2).

## Current state

`CodeSourceStrategy` (5.1) selects a code-only project's source files, but nothing turns code into the feature-level meaning the store requires — and nothing pins the shape of how it will. `CodeDistiller` is consumed by two downstream tasks (5.3's bootstrap, 5.4's episodic code-derivation), so its interface needs to be stable before either builds on it. Its most load-bearing invariant — "bounded units, per package/module, never the whole codebase in one prompt" — is asserted only in prose today. A grouping bug that lets one unbounded prompt slip through (e.g. treating an entire large repo as one "unit") doesn't crash; it silently truncates or degrades the distilled output, with no exception raised.

## Change

Define `CodeDistiller`'s signature and the bounded-unit grouping/composition mechanics — the deterministic, mockable part of this task — and pin it with red tests before writing the real LLM-prompting logic. LLM-output *quality* (features vs. a symbol dump) is explicitly out of scope here; that's an eval-harness concern, unchanged, and lands in 5.2.2.

- `src/knowledge/code_distiller.py`:
  - `CodeDistiller.distill(repo: str, paths: list[str]) -> str` — a STUBBED method (raises `NotImplementedError` for now).
  - the grouping logic: partition `paths` into **bounded units** (per package/module — never the whole codebase in one prompt); this partitioning is pure, no LLM call.
  - the composition logic: given per-unit description strings (in the real implementation, LLM outputs; in these tests, whatever a mocked `LLMClient` returns), concatenate them into one feature-level text for the repo/scope.
- Write red tests over a **mocked `LLMClient`** (never a real model call) pinning:
  - N paths spanning M distinct packages/modules → the grouping produces M bounded units, never fewer (collapsing modules) or one giant unbounded unit;
  - every path in the input is covered by exactly one unit — no path dropped, no path duplicated across units;
  - the composed output concatenates each unit's (mocked) per-unit result, in a stable order.

## Files & types

- new `src/knowledge/code_distiller.py` (`CodeDistiller`, stub `distill` + grouping/composition helpers)
- new test file(s) covering the grouping and composition cases above, run against a mocked `LLMClient` (red)

## Guards

- Tests-first: the stub raises on `distill` itself, but the grouping/composition helpers are pure and directly testable without a real LLM — 5.2.2 wires them to real prompting, it does not redesign them.
- **Bounded units are asserted mechanically** — a test plants a large `paths` list spanning many modules and asserts the unit count, not just "it ran without error."
- LLM-output quality (delivered-behavior features vs. a symbol dump) is explicitly **not** tested here — that stays the eval harness's job in 5.2.2, evaluated against a user-authored reference, not a unit-testable assertion.

## Verification

- The grouping/composition test suite added here is red only where the logic doesn't exist yet (stub raises) — once implemented, it passes without any LLM call (mocked throughout).
- Each of the three pinned cases (unit count matches module count, full path coverage with no duplication, stable-order composition) has a corresponding red test.
