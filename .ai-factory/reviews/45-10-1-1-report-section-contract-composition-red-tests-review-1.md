# Code Review: 10.1.1 — Report section contract + composition (red tests)

**Scope reviewed:** `src/changelog/{__init__,section,report}.py`, `src/core/config.py`, `tests/changelog/{__init__,conftest,test_report,test_schedule}.py`
**Plan:** `.ai-factory/plans/45-10-1-1-report-section-contract-composition-red-tests.md`
**Governing spec:** `.ai-factory/specs/50-digest-section-report-contract.md`

## Method
- Read every changed/new file in full and cross-checked against the plan and spec.
- Ran the new suite: `pytest tests/changelog` → **12 passed**.
- Ran the full suite to confirm the `config.py` change regresses nothing: `pytest` → **129 passed**.
- Checked for a configured linter/formatter (none present in `pyproject.toml`), so line length is not a CI surface.

## Correctness verification

- **`Report.build` composition mechanics** match the spec exactly: the window is resolved once (`await self.window.resolve(repo)`), each section is rendered in order with the same `(before, after)` + `lang`, `None` results are dropped, all-`None` → `None`, survivors joined with `"\n\n"`. Sequential `await` preserves order with no concurrency hazard. Verified by `test_report.py` (order/None-drop, all-None, single-survivor, resolve-once-and-shared, lang threading + default, repo/org_id threading).
- **`ReportSection` / `ReportWindow` ABCs** follow the established `@abstractmethod` + `...` style (`localizer.py`, `store.py`); `render`/`resolve` signatures match the spec (`render(repo, org_id, before, after, lang="ru") -> str | None`; `resolve(repo) -> tuple[str, str]`, no `org_id`).
- **`TimeWindow`** is a frozen dataclass carrying `delta`; equality-by-value holds (`TimeWindow(timedelta(days=1)) == TimeWindow(timedelta(days=1))`), and it is instantiable because it overrides the abstract `resolve` (deferring the git range to 10.2 via `NotImplementedError`, as the plan scopes). Correct.
- **`schedule_by_name` / `report_for_schedule`** resolve name → window + ordered sections, raise `ValueError` naming the first unknown section key, and raise `ValueError` on an unknown schedule name. Order is preserved. Matches the spec's "unknown section key = startup error" guard (the registry is passed in from the composition root, per plan). Verified by `test_schedule.py`.
- **`Settings.report_schedules`** uses the established `Annotated[..., NoDecode]` + before-validator pattern. Confirmed runtime behavior:
  - Env/programmatic JSON string → parsed to `tuple[ReportSchedule, ...]` (test passes; pydantic v2 validates the stdlib frozen dataclass natively and value-equality survives revalidation).
  - Unset field → default `()` (before-validator is not run on defaults, since `validate_default` is off), so no premature `json.loads`. Correct.
  - Empty string `""` → validator returns `()`. Correct.
  - `ReportSchedule` is defined above `Settings`, so the forward reference in the annotation resolves.
- **Dependency direction** is correct: `changelog.report → core.config` (feature → infra); `core.config` imports nothing from `changelog`; no import cycle. `report.py` depends on `section.py` within the feature.
- **No migrations, DB, I/O, or external boundary** are introduced — nothing to break at runtime beyond the intentionally-deferred `TimeWindow.resolve`.

## Non-blocking observation (not a defect)

- `_parse_report_schedules` (`src/core/config.py`) handles the two real input shapes — a raw JSON **string** (env) and an already-built tuple/list of `ReportSchedule` (programmatic). If a caller were to pass a Python **list of dicts** directly (`Settings(report_schedules=[{...}])`), the `all(isinstance(item, ReportSchedule) ...)` guard is `False` and control falls to `json.loads(value)`, which raises `TypeError` on a list rather than parsing it. This path is not exercised by env (always a string), the default (skipped), or the tests, and is not a documented usage — so it is not a live bug. Mirrors the existing `_parse_json_dict` / `_parse_project_edges` validators, which likewise assume a string on the non-preparsed path. Flagged only for awareness; no change required for this task.

## Conclusion
All guards and verification points from the spec are implemented and covered by deterministic tests; the full suite is green and nothing regressed. No correctness, security, or runtime-breakage findings.

REVIEW_PASS
