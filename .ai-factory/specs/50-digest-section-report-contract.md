# 10.1.1 — Report section contract + composition (red tests)

**Phase:** 10 — Reporting engine (composable reports). Depends on 4.2 (resolver), Phase 3 (mirror + source strategy), 8.1 (the reasoner's narration). Lays the composition seam the section impls (10.1.2) green.

## Current state

A report (daily, weekly, and — later — release) is not one fixed shape: it is a composition of independent content blocks over a time window, delivered as one text. Nothing defines that seam. Hardcoding "daily = per-branch, weekly = holistic" would bury the report shape in code — adding "weekly with a per-branch block" would mean a rewrite. The composition must be data; each block a self-contained unit.

## Change

Define the section seam, the report composition, and the schedule config — with red tests over the composition mechanics. No section bodies, no real narration.

- `src/changelog/section.py` — `ReportSection` (ABC): `render(repo: str, org_id: int, before: str, after: str, lang: str = "ru") -> str | None`. One self-contained content block; receives the report's **already-resolved** range and returns its text, or `None` when it has nothing for that range. `lang` (default the lowercase `"ru"` `narrate`/the localizer use) is threaded from `Report.build` so a section that narrates produces its text in that language — 10.3's localizer drives per-language builds through this same parameter, and 10.1.2's sections pass it straight into `Reasoner.narrate(change, lang)`. Stub raises.
- `src/changelog/report.py`:
  - `ReportWindow` (ABC) — `resolve(repo) -> (before, after)`: resolves the report's window to a commit range on the mirror. Phase 10 ships `TimeWindow(timedelta)` (a day / a week); Phase 11 adds `SinceDeployWindow` (11.2.1). `Report` holds a `ReportWindow` and passes the resolved range to its sections. **Precondition:** `resolve(repo)` and every section read their range/content on an **already-ensured** bare mirror — neither the window nor a section ever calls `mirror.ensure` itself, since `resolve(repo)` carries no `org_id` by design (`mirror.ensure` needs one to mint the GitHub token). The caller holding `(repo, org_id)` owns `mirror.ensure(repo, org_id)` before `Report.build` — 10.2's entrypoint for scheduled reports, the release fan-out for release notes (11.3).
  - `Report` — composes an ordered `list[ReportSection]` over a `ReportWindow`: `build(repo, org_id, lang: str = "ru") -> str | None` resolves the window **once** (`window.resolve(repo)`), renders each section in order with that same `(before, after)` and `lang`, **drops the `None` ones**, and joins the rest with a blank line (`"\n\n"`) into one text; when **every** section is `None`, the whole report is `None`.
- `Settings.report_schedules` — the composition as config, parsed as JSON (like `canonical_refs`/`github_org_logins`, `src/core/config.py`): a list of `{"name": str, "window": <days:int>, "sections": [<key>, …]}`. `window` is a whole-day count the entrypoint (10.2) builds into `TimeWindow(timedelta(days=window))`; `sections` is an ordered list of section keys. A schedule name resolves to a window + an ordered section list; a key absent from the composition root's section registry is a **startup error**. Adding a report, or a block to one, is a config edit — never code.

## Files & types

- new `src/changelog/section.py` (`ReportSection` ABC, stub), `src/changelog/report.py` (`ReportWindow`, `Report`)
- extend `src/core/config.py` (`report_schedules` shape + parse)

## Guards (red tests — deterministic, no LLM)

- A section returning `None` is **dropped** from the assembly — never rendered as empty text or the literal "None"; the report is the join of the non-`None` sections only.
- Section **order is preserved** in the assembled text.
- **All sections `None` → report `None`** (10.2 delivers nothing) — the silent trap is delivering an empty/whitespace report.
- **The window is resolved exactly once per `build`** — every section renders against the same `(before, after)`; a section re-resolving its own window could silently see a different range than its siblings.
- The schedule config maps a name → the correct window + ordered section list; an **unknown section key is a startup error**, not a silently skipped block.
- Sections are stubbed (raise); the composition is tested over fake sections returning fixed strings / `None`.
- **The mirror-ensured precondition is the caller's, never this seam's** — `ReportWindow.resolve(repo)` and every section read an already-ensured bare mirror; neither calls `mirror.ensure` (no `org_id` on `resolve`). This is a caller-side precondition, not composition mechanics — no red test here for it.

## Verification

- A report over `[secA→"A", secB→None, secC→"C"]` → `"A\n\nC"` (order kept, `None` dropped).
- A report where every section returns `None` → `build` returns `None`.
- A fake `ReportWindow.resolve` is called exactly once per `build`, and every section receives that same `(before, after)`.
- `report_schedules` with `{"name":"daily","window":1,"sections":["summary","per_branch","remaining"]}` resolves to `TimeWindow(timedelta(days=1))` + those three keys in order; an unknown key raises at startup.
