# Plan: 10.1.1 — Report section contract + composition (red tests)

## Context
Lay the composition seam for reports: a `ReportSection` block contract, a `Report` that composes ordered sections over a `ReportWindow` (resolved once, `None` dropped, joined with `\n\n`), and `Settings.report_schedules` (composition as config), pinned by deterministic contract tests over fake sections/windows. No section bodies, no narration, no LLM.

## Settings
- Testing: yes
- Logging: minimal
- Docs: no

## Assumptions & scope notes
- **Section bodies are out of scope.** `section.py` ships only the `ReportSection` ABC. The three real section impls (`SummarySection`, `PerBranchSection`, `RemainingSection`) are added in 10.1.2. Composition is tested with **fake** sections/windows only ("stubbed sections" = the fakes in tests).
- **`TimeWindow.resolve` (git range over the mirror) is deferred to 10.2.** This task only needs `TimeWindow` to be a constructible, equatable `ReportWindow` carrying its `timedelta` so the schedule resolver can build `TimeWindow(timedelta(days=<window>))` and the verification can assert on it. Its `resolve(repo)` raises `NotImplementedError` here (the mirror wiring lands with the 10.2 entrypoint). `Report.build`'s composition tests use a **fake** `ReportWindow`, never `TimeWindow`, so this deferral does not weaken the composition guards.
- **The section registry lives at the composition root (10.2), not here.** This task provides a resolver helper that validates schedule section keys against a *passed-in* registry; the unknown-key "startup error" is exercised by passing a registry that lacks the key.
- **ABC naming follows the established project convention** (`LLMClient`, `KnowledgeStore`, `Localizer`, and the spec's own `ReportWindow`/`ReportSection`): descriptive names, no `I`-prefix. The spec pins these exact names.
- **`ReportSchedule` (config DTO) lives in `src/core/config.py`** so config parsing owns its shape and the dependency direction stays feature → core (never core → changelog). `report.py` imports `ReportSchedule` from `core.config`.

## Tasks

### Phase 1: Contracts & composition

- [x] **Task 1: `ReportSection` ABC**
  Files: `src/changelog/__init__.py`, `src/changelog/section.py`
  Create the `src/changelog/` package (`__init__.py`). In `section.py`, define `ReportSection(ABC)` with a single abstract async method `render(self, repo: str, org_id: int, before: str, after: str, lang: str = "ru") -> str | None`. One self-contained content block over an **already-resolved** `(before, after)` range; returns its text or `None` when it has nothing for that range. Follow the ABC style already used in `src/reasoning/localizer.py` / `src/knowledge/store.py` (`@abstractmethod` + `...` body, docstring describing behavior). Docstring must state the caller precondition: the range is resolved once by `Report` and the bare mirror is already ensured by the caller — a section never calls `mirror.ensure`.

- [x] **Task 2: `ReportWindow` ABC, `TimeWindow`, and `Report` composition**
  Files: `src/changelog/report.py`
  - `ReportWindow(ABC)`: abstract async `resolve(self, repo: str) -> tuple[str, str]` returning the `(before, after)` commit range on the already-ensured bare mirror. Docstring: `resolve` carries no `org_id` by design and never calls `mirror.ensure` (caller's precondition).
  - `TimeWindow(ReportWindow)`: a frozen `@dataclass` carrying `delta: timedelta` (so equality is by `delta` — `TimeWindow(timedelta(days=1)) == TimeWindow(timedelta(days=1))`). Its `resolve` raises `NotImplementedError` with a message noting the git-range resolution lands in 10.2. Import `timedelta` from `datetime`.
  - `Report`: constructed with a `ReportWindow` and an ordered `list[ReportSection]`; expose them as public read attributes (`window`, `sections`) for assertion in tests. `async def build(self, repo: str, org_id: int, lang: str = "ru") -> str | None`:
    1. Resolve the window **exactly once**: `before, after = await self.window.resolve(repo)`.
    2. Render each section **in order** with that same `(before, after)` and `lang`, awaiting each.
    3. **Drop `None`** results (never render as `""` or the literal `"None"`).
    4. If **no** section produced text → return `None`.
    5. Otherwise join the surviving texts with `"\n\n"` and return the single string.
  Class docstring must state: window resolved once per `build`; every section sees the same range; `None` dropped; all-`None` → `None`.

- [x] **Task 3: `ReportSchedule` config DTO + `Settings.report_schedules`** (depends on Task 2)
  Files: `src/core/config.py`
  - Add a frozen `@dataclass` `ReportSchedule` with `name: str`, `window: int` (whole-day count), `sections: tuple[str, ...]` (ordered section keys). Place it above `Settings` in `config.py`.
  - Add field `report_schedules: Annotated[tuple[ReportSchedule, ...], NoDecode] = ()` to `Settings`, mirroring the existing `NoDecode` + `field_validator(mode="before")` pattern used for `canonical_refs` / `project_edges`.
  - Add a `field_validator("report_schedules", mode="before")` that: returns the value unchanged if already a tuple/list of `ReportSchedule`; returns `()` for empty/falsey; otherwise `json.loads` a JSON array of `{"name": str, "window": int, "sections": [str, ...]}` objects and builds `tuple(ReportSchedule(name=o["name"], window=int(o["window"]), sections=tuple(o["sections"])) for o in parsed)`. Keep the `sections` order as given in the JSON.

- [x] **Task 4: Schedule → `Report` resolver with registry validation** (depends on Task 2, Task 3)
  Files: `src/changelog/report.py`
  Add two module-level helpers in `report.py` (importing `ReportSchedule` from `src.core.config`, and `timedelta` from `datetime`):
  - `schedule_by_name(schedules: Iterable[ReportSchedule], name: str) -> ReportSchedule` — return the schedule whose `name` matches; raise `ValueError` (clear message) if no schedule has that name.
  - `report_for_schedule(schedule: ReportSchedule, registry: Mapping[str, ReportSection]) -> Report` — build `TimeWindow(timedelta(days=schedule.window))`, look up each key in `schedule.sections` (in order) against `registry`, and construct `Report(window, [registry[key] for key in schedule.sections])`. If **any** key is absent from `registry`, raise `ValueError` naming the missing key (this is the composition-root startup error). Preserve section order.
  Type-hint with `collections.abc.Iterable` / `collections.abc.Mapping`.

### Phase 2: Contract tests (red — deterministic, no LLM)

- [x] **Task 5: Test scaffolding + fakes** (depends on Task 1, Task 2)
  Files: `tests/changelog/__init__.py`, `tests/changelog/conftest.py`
  Create the test package and a `conftest.py` with deterministic fakes (async, mirroring the fake style in `tests/reasoning/conftest.py`):
  - `FakeSection(ReportSection)` — constructed with a fixed return value (`str | None`); its `render` records every call as `(repo, org_id, before, after, lang)` on a `calls` list and returns the fixed value. Used to assert every section receives the same `(before, after)` + `lang`.
  - `CountingWindow(ReportWindow)` — constructed with a fixed `(before, after)`; its `resolve` increments a `resolve_count` and records the `repo` it was called with, returning the fixed range. Used to assert the window resolves exactly once per `build`.
  Provide pytest fixtures for convenient construction if it reduces duplication (tests run under `asyncio_mode = "auto"`, so async test funcs need no marker).

- [x] **Task 6: Composition mechanics tests** (depends on Task 5)
  Files: `tests/changelog/test_report.py`
  Cover the composition guards over fake sections/window:
  - **`None` dropped, order preserved:** `[secA→"A", secB→None, secC→"C"]` ⇒ `build(...) == "A\n\nC"` (no empty line for the dropped section, no `"None"` text).
  - **All-`None` → `None`:** every section returns `None` ⇒ `build(...) is None`.
  - **Single surviving section:** exactly one non-`None` ⇒ that section's text, no join artifacts.
  - **Window resolved exactly once:** using `CountingWindow`, assert `resolve_count == 1` after one `build`, and that **every** `FakeSection` recorded the same `(before, after)` the window returned.
  - **`lang` threaded:** `build(repo, org_id, lang="de")` ⇒ every section's recorded `lang == "de"`; default call records `"ru"`.
  - **`(repo, org_id)` threaded:** each section receives the `build` call's `repo`/`org_id`.

- [x] **Task 7: Schedule config + resolver tests** (depends on Task 3, Task 4, Task 5)
  Files: `tests/changelog/test_schedule.py`
  - **Config parse:** construct `Settings(github_webhook_secret="x", telegram_bot_token="x", report_schedules='[{"name":"daily","window":1,"sections":["summary","per_branch","remaining"]}]')` (JSON string, as env would supply) and assert it parses to one `ReportSchedule(name="daily", window=1, sections=("summary","per_branch","remaining"))`. Also assert empty/unset ⇒ `()`. (Follow the direct-`Settings(...)` construction style in `tests/routing/test_role_for_branch.py`.)
  - **Name → window + ordered sections:** with a registry of fake sections keyed `{"summary":…, "per_branch":…, "remaining":…}`, `report_for_schedule(schedule_by_name(schedules, "daily"), registry)` yields a `Report` whose `window == TimeWindow(timedelta(days=1))` and whose `sections` are exactly `[registry["summary"], registry["per_branch"], registry["remaining"]]` in that order.
  - **Unknown section key = startup error:** a schedule referencing a key missing from the registry ⇒ `report_for_schedule(...)` raises `ValueError` (assert the missing key is named).
  - **Unknown schedule name:** `schedule_by_name(schedules, "nope")` raises `ValueError`.
