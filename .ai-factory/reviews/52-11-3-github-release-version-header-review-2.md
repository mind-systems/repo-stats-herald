# Code re-review: 11.3 — GitHub release + version header (round 2)

Re-review after fixes for [review 1](52-11-3-github-release-version-header-review-1.md). All cited files re-read from disk (not session memory).

## Verdicts on previous findings

### Finding 1 [Low/latent] — `app_available` is not a strict bool
**Status: Fixed.**

Previous content at `src/ingestion/router.py:71`:
```python
app_available = changelog_client is not None and base_url
```
Current content at `src/ingestion/router.py:71` (re-read):
```python
app_available = changelog_client is not None and bool(base_url)
```
The `bool(base_url)` coercion makes the expression a strict `bool` in both operands' outcomes: `changelog_client is None` short-circuits to `False`, and `changelog_client is not None` yields `True and bool(base_url)` → `bool`. Combined with the `except` branch's `app_available = False`, every assignment of the local is now a genuine boolean, so the 12.2 hand-off local is safe to consume as a flag. Confirmed by reading lines 69–78 in full.

## Full re-review for new issues

Ran `git status` / `git diff HEAD`; re-read every changed source file in full.

- `src/ingestion/router.py` — only line 71 changed since round 1 (the fix above); the rest of `_deliver_release` and the webhook registration are byte-identical to the previously-reviewed, verified version.
- `src/delivery/github_release.py`, `src/delivery/service.py`, `src/main.py`, `src/routing/models.py`, `tests/ingestion/test_release_delivery.py` — unchanged from round 1 (`git diff` confirms).

Re-verified the properties that matter:
- Fan-out order: `mirror.ensure` → `versioner.next` → early-return on `None` version → union → single `report_notes` → `create` → version-headed `deliver`.
- `prerelease = role is BranchRole.STAGING`; `target_commitish=event.after`; `owner=event.org_login`; `org_id` threaded for token minting.
- Union degradation catches `config` failure before `union |=`, leaving `{plan.language, plan.github_release_language}`; release + Telegram still fire.
- `DeliveryService.deliver` stays backward-compatible with the no-`version` Phase-10 report path.
- No import cycles; `getattr(plan, "changelog_base_url", None)` safe on the frozen `slots` `DeliveryPlan`.

Full suite: **187 passed** (`uv run pytest -q`).

No new bugs, security issues, or correctness problems found.

REVIEW_PASS
