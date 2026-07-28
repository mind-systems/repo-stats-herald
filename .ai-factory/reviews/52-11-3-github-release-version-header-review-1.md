# Code review: 11.3 — GitHub release + version header

## Scope
Reviewed the code changes for this task:
- `src/routing/models.py` — `DeliveryPlan.github_release_language`
- `src/delivery/github_release.py` — new `GitHubReleaseClient`
- `src/delivery/service.py` — version header on the Telegram delivery
- `src/ingestion/router.py` — `_deliver_release` fan-out + staging/release registration
- `src/main.py` — composition-root wiring
- `tests/ingestion/test_release_delivery.py` — fan-out behaviour tests

Each file read in full against its collaborators. Full suite run: **187 passed** (incl. the 7 new fan-out tests and the unchanged webhook-contract / delivery tests).

## Verification performed
- Ran `uv run pytest` — all green, no regressions.
- Confirmed `DeliveryPlan` is a frozen `slots` dataclass with the new `github_release_language="en"` default; `getattr(plan, "changelog_base_url", None)` returns `None` safely (field genuinely absent until 12.1), so the dormant changelog leg is correct.
- Confirmed the fan-out sequences collaborators correctly: `mirror.ensure` first → `versioner.next` (sync, correct arg order `repo, role, before, after`) → early-return on `None` version → union → single `report_notes` → `create` → version-headed `deliver`.
- Confirmed `prerelease` is derived from `role is BranchRole.STAGING` (no inline branch-string compare), `target_commitish=event.after`, `owner=event.org_login`, `org_id=event.org_id`.
- Confirmed the union degradation: the `config` failure is caught *before* `union |=`, so the union stays `{plan.language, plan.github_release_language}` and the release + Telegram still fire.
- Confirmed backward compatibility of `DeliveryService.deliver` — the Phase-10 report path (`scripts/report.py`) calls `deliver(plan, text)` with no `version`, so no header is added.
- Confirmed no import cycle (`delivery → versioning`, `github_release → versioning`; versioning imports neither).
- Confirmed the webhook handler's collaborator gather uses `getattr(..., None)` and an `all(...)` guard, so a lifespan that did not run (GitHub App disabled, or `TestClient` without context) simply logs "skipped" and returns the unchanged `JSONResponse` — the existing contract tests still pass.

## Findings

### 1. [Low / latent] `app_available` is not a strict bool — a trap for the 12.2 hand-off
`src/ingestion/router.py:71`
```python
app_available = changelog_client is not None and base_url
```
Because `base_url` is `str | None`, this expression evaluates to `None` (when unset) or the URL **string** (when set) — never a real `bool`. Verified at runtime: `app_available` is `None` or `'http://x'`.

Impact on **11.3 is nil**: the only use is `if app_available:`, and the truthiness is correct. However, the adjacent comment explicitly designates `app_available` as one of the locals "a later `entry` call continues from" (12.2). A 12.2 author who does `ChangelogEntry(... , available=app_available)`, serializes it, or compares `app_available is True` will get a URL/`None` instead of a boolean. Recommend normalizing now: `app_available = changelog_client is not None and bool(base_url)` (and it is reassigned to `False` in the `except`, so the two branches would then agree on type).

No other bugs, security issues, or correctness problems found. The implementation matches the plan and the task spec (one `report_notes` per push, `str(version)` as the single render path, role-derived prerelease, `event.after` commitish, `None` version cuts nothing, unreachable app never blocks the other channels).
