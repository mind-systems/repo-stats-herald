## Code Review Summary

**Files Reviewed:** 1 plan (`54-12-2-changelog-channel-wiring.md`) against `src/ingestion/router.py`, `src/main.py`, `src/delivery/changelog_client.py`, `src/reasoning/localizer.py`, `src/routing/{models,resolver}.py`, `src/versioning/versioner.py`, `tests/ingestion/test_release_delivery.py`, spec `23-changelog-channel-wiring.md`, roadmap line 12.2.
**Risk Level:** 🟢 Low

The plan is well-grounded. Every line/file reference I checked is accurate (`router.py:55/62-65/70-78/93-95/190-195/192`, `main.py:112-113`, `changelog_client.py:27`). The three ground-truth deviations are all real and correctly reasoned:
- **Deviation #1** (fan-out lives in `router.py::_deliver_release`, not `service.py`) is verified — the function holds every local the `entry` call needs and `DeliveryService` is a Telegram-only transport. The spec's `service.py` file hint is legitimately overridden by code; this is conformance, not drift.
- **Deviation #2** (`app.state.changelog_client` never registered) is verified — `router.py:192` threads it via `getattr(..., None)` but nothing sets it, so the channel is dormant.
- **Deviation #3** (`config.languages` vs `list[str]` contract-drift bug) is verified — `changelog_client.py:31` returns `response.json()["languages"]` (a list), so `config.languages` at `router.py:75` would `AttributeError`, be swallowed, and force `app_available=False`. The test fake (`FakeChangelogConfig`, line 115-129) masks it. Excellent catch; the fix is correct and necessary for the channel to fire at all.

No KeyError risk on `notes[lang]`: `union |= set(declared_languages)` guarantees `report_notes` (which returns keys == `langs`) covers every declared language. The `str(version)`, `github_url`, `role`, and reuse-once claims all hold against the code.

### Context Gates
- **Architecture (WARN):** `_deliver_release` is a growing module-level orchestration inside a router, which sits against ARCHITECTURE.md's "routers/CLIs are thin; services own business logic" rule (lines 82, 95). This is a **pre-existing** condition introduced by 11.3, and the plan's Deviation #1 reasonably extends the established pattern rather than splitting the changelog protocol across two modules. Not a blocker for 12.2 — see Deferred observations.
- **Rules:** `RULES.md` is intentionally empty — no counter-defaults; nothing to violate.
- **Roadmap:** Plan heading matches ROADMAP line 12.2 and spec 23. The plan honors every guard in the spec (one-place role→environment map, zero re-derivation, last-leg-after-Telegram ordering, caught+logged failure, unmapped-repo skip, declared-languages-only summaries). Composition-root registration (Task 1) is consistent with the "wire concretes only at the composition root" pattern and correctly co-located with the other release-delivery collaborators so the channel only activates when the full fan-out exists.

### Critical Issues
None.

### Issues

1. **Stale `_deliver_release` docstring not updated (`src/ingestion/router.py:44-54`).** The plan replaces the extension-point comment at `router.py:93-95` (Task 3) but leaves the function docstring, whose second paragraph states the changelog leg *"is dormant until the changelog app itself is wired"*. After Tasks 2–3 the leg fires, making that paragraph factually wrong. `router.py` is a file this task edits, so per scope this is a finding, not deferred. The plan should add a step to rewrite that paragraph to describe the now-active leg (still noting the unreachable-app degrade-to-fixed-channel behavior, which remains true).

2. **`summaries` can carry `None` values, diverging from the codebase's `or ""` coercion (`src/ingestion/router.py`, Task 3 payload).** `PivotLocalizer.report_notes` returns `dict[str, str | None]` and maps **every** language to `None` when `report.build` returns `None` (empty report — `localizer.py:84-85`). The plan's `summaries={lang: notes[lang] for lang in declared_languages}` would then post `{ru: null, en: null, ...}`. The GitHub release body (`router.py:88`) and Telegram note (`router.py:97`) both coerce with `notes.get(...) or ""`; the changelog leg does not, so it can emit `null`s over the wire against a `summaries: object` of strings. Recommend the plan either coerce (`notes[lang] or ""`, mirroring the sibling channels) or explicitly justify posting raw values. Low likelihood on a version-bumping push (new commits usually yield a non-empty summary), but the coercion inconsistency is real and fixable within `router.py`.

### Minor / Nits
- Task 3 phrasing: *"Add `from src.delivery.changelog_client import ChangelogEntry` and `from src.routing.models import BranchRole` (BranchRole is already imported)"* — the parenthetical resolves it, but an implementer following the imperative literally could add a duplicate `BranchRole` import (already present at `router.py:15`). Consider dropping `BranchRole` from the "add" instruction.

### Positive Notes
- Deviation #3 (the `config.languages` latent bug) is a genuinely valuable find that the existing green tests actively concealed; fixing the fake alongside the client is the right call.
- The zero-re-derivation guard is honored concretely — reusing `role`, `version`, `github_url`, `notes`, and the single `declared_languages` with no second `config`/`report_notes`/`role_for_branch`/`str(...)` — and the plan adds an explicit test asserting the call counts.
- `_ENVIRONMENT_BY_ROLE` as a module-level constant satisfies the spec's "one place" mapping guard cleanly.
- Test plan mirrors the spec's verification matrix exactly (mapped-reachable staging, release→production, unmapped skip, unreachable-at-`entry`, zero-re-derivation, None-version).

## Deferred observations
- Affects: Phase 11 / 12 (`src/ingestion/router.py::_deliver_release`) — the release fan-out is a growing module-level orchestration living in the ingestion router, in tension with ARCHITECTURE.md's "routers are thin, services own business logic" guidance. This originates in 11.3 and is out of 12.2's scope; whether to extract it into a delivery-side service (as the spec's original `service.py` hint envisioned) is a structural decision for the phase, not this task. The plan's inline placement is the correct local choice given the current shape.
