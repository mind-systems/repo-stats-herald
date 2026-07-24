# 10.2 — Report schedules + delivery

**Phase:** 10 — Reporting engine (composable reports). Depends on 10.1.1/10.1.2 (report + sections), 3.5 (served-repo set), Phase 9 (delivery). Closes the phase: each configured schedule fires on its cadence and reaches every served project's channel.

## Current state

The report composition (10.1.1) and its sections (10.1.2) build a report on demand, but nothing runs a schedule or delivers it. The authoritative served-repo set — with `org_id` — is the `served_repos` table (3.5).

## Change

Add one config-driven entrypoint that builds and delivers a named schedule's report for each served project.

- `scripts/report.py --schedule <name>` — a composition-root entrypoint: assembles a `RepoMirror` (as `scripts/summarize_range.py` does) and injects it into the windows/sections; looks up the schedule in `Settings.report_schedules` (10.1.1) → its window + ordered sections → assembles a `Report`; for each `(repo, org_id)` in the **`served_repos` table (3.5)**, calls **`mirror.ensure(repo, org_id)` before `Report.build(repo, org_id)`** — so the window `resolve` and every section read an already-fetched bare store — and where `build` returns text, resolves a delivery plan and `DeliveryService.deliver(plan, report)` (Phase 9) to the org's Telegram channel.
- **Cadences are config + cron** — daily and weekly are two entries in `report_schedules` (e.g. `daily={1d, [summary, per_branch, remaining]}`, `weekly={7d, [summary]}`), each invoked by its own cron with `--schedule`. A new report, or a per-branch block added to the weekly, is a config edit — no code, no new task.
- Delivery plan for a report — a report has **no single branch**. Resolve the plan via the repo's canonical ref (the 3.6 policy value); only `plan.telegram_channel` and `plan.language` are consumed, `plan.branch_role` is **not** read.

## Files & types

- new `scripts/report.py` (entrypoint, `--schedule`)

## Guards

- **Iterate `served_repos` (3.5), not the mirror-root listing** — authoritative set, carries `org_id`; a de-served repo's leftover mirror must not deliver, and `org_id` must not be guessed from a directory name.
- A repo whose report `build` returns `None` produces and delivers nothing (common for a quiet daily window).
- Cadence delivery consumes only `telegram_channel` + `language` — never `branch_role`/`is_release`/`is_prerelease` (those gate milestone delivery, Phase 11).
- Delivered through `DeliveryService` (Telegram, RU) — an org with no mapped channel is logged, not posted.
- Idempotent: a re-run in the same window rebuilds and re-delivers the same report.
- Assembly only — iterate → ensure → build → resolve-plan → deliver; the report shape lives in config, not here.
- **The report pipeline reads the mirror at every layer** (window `resolve` + all sections) but none of them ensure it — `ReportWindow.resolve(repo)` carries no `org_id` (10.1.1/11.2.1), so it structurally cannot call `mirror.ensure`. This entrypoint owns `mirror.ensure(repo, org_id)`, once per served repo, before `build`. The report cron is decoupled from the push path, so it never assumes a push already ensured the mirror.

## Verification

- `--schedule daily` (resp. `weekly`) builds+delivers each served repo's report for that schedule's window+sections, to its org channel.
- A repo in the mirror root but absent from `served_repos` → nothing.
- A quiet window → report `None` → nothing posted.
- Re-running in-window delivers the same report (idempotent).
- Adding a section key to a schedule's `sections` in config changes the delivered report with no code change.
- A served repo whose mirror is absent or stale at cron time → the entrypoint ensures it before building, so the report reflects current history, not an empty or stale store.
