# Code Review (Round 2 — re-review after fixes): 3.6 — Populate and keep fresh

Re-read every file cited in `20-3-6-populate-and-keep-fresh-review-1.md` fresh from disk, then ran the full test suite and import sanity. Verdicts per prior finding, then a fresh pass for new issues.

## Verdicts on Round-1 findings

### Finding 1 — HIGH: empty `.env` values crash `Settings()` — **FIXED**

`src/core/config.py:24-25` now marks both dicts `NoDecode` and routes them through a validator that treats empty/falsy as `{}`:

```python
    canonical_refs: Annotated[dict[str, str], NoDecode] = {}
    github_org_logins: Annotated[dict[int, str], NoDecode] = {}
```
```python
    @field_validator("canonical_refs", "github_org_logins", mode="before")
    @classmethod
    def _parse_json_dict(cls, value: object) -> object:
        if isinstance(value, dict):
            return value
        if not value:
            return {}
        return json.loads(value)
```

Verified empirically with a `.env` carrying the empty `CANONICAL_REFS=`/`GITHUB_ORG_LOGINS=` lines (the copy-the-template case that broke before):

```
empty OK -> {} {}
json OK -> {244165546: 'mind-systems'} int {'repo': 'main'}
```

Empty values now yield `{}` instead of `SettingsError`, and a real JSON value still parses with `github_org_logins` keys coerced to `int`. The whole test suite (29 passed) and `import src.main, scripts.backfill` both succeed.

### Finding 2 — MEDIUM: `backfill` crashes on a binary file under `docs/` — **FIXED**

`src/knowledge/indexer.py:36-40` now guards the read:

```python
        try:
            text = (tree / path).read_text(encoding="utf-8")
        except UnicodeDecodeError:
            logger.debug("skipping %s:%s — not valid UTF-8", repo, path)
            return
```

A binary asset under `docs/` (e.g. `docs/img/diagram.png`) is now log-skipped instead of aborting the walk, so `backfill` survives a real repo with non-UTF-8 files under a selected prefix.

### Finding 3 — LOW: `clone_source` `KeyError` for an org missing from the map — **FIXED**

Both composition roots now use `.get` + an explicit, legible error. `src/main.py:44-47`:

```python
        def clone_source(repo: str, org_id: int) -> str:
            login = settings.github_org_logins.get(org_id)
            if login is None:
                raise LookupError(f"no GITHUB_ORG_LOGINS entry for org_id={org_id}")
            return f"https://github.com/{login}/{repo}.git"
```

`scripts/backfill.py:44-48` carries the identical guard. A served org absent from the map now fails with a clear `LookupError` naming the org id rather than a bare `KeyError` deep inside `RepoMirror.ensure`.

### Finding 4 — LOW (deferred): blocking git ops on the event loop — **Not fixed (as expected)**

`src/knowledge/sync.py` still calls the blocking `RepoMirror.ensure/tree/default_branch` inside the `on_push` background task. This was explicitly deferred in Round 1 as acceptable for the single-tenant slice; no change was expected. Still worth revisiting (thread/executor offload) when webhook concurrency matters.

## Fresh pass — new issues

Re-read all changed files in full (`config.py`, `.env.example`, `mirror.py`, `sync.py`, `main.py`, `router.py`, `indexer.py`, `backfill.py`) and re-checked the fixes for regressions:

- The `_parse_json_dict` validator is correct for both the `NoDecode` env-string path (`json.loads` → pydantic coerces `github_org_logins` keys to `int`) and the passthrough-dict/default path (`isinstance(value, dict)` and the `not value` guard). Malformed JSON still raises at boot — appropriate fail-loud for an operator-supplied value.
- The `UnicodeDecodeError` guard is scoped tightly to the `read_text` call and returns before chunk/embed/upsert, so a skipped binary does no store work and does not leave partial chunks.
- The `LookupError` in `clone_source` fires inside `RepoMirror.ensure`; in the `on_push` background-task path it surfaces only in server logs (the HTTP ack already went out), which is the same acceptable failure mode discussed in Finding 4 — not a new issue.
- Full suite: **29 passed**. The webhook-contract tests remain green (lifespan-less `TestClient(app)` → `knowledge_sync` unset → `on_push` skipped, push still returns 200 + event).

Remaining nit (unchanged, harmless): `KnowledgeSync._canonical_ref` accepts `org_id` but never uses it.

No new correctness, security, or runtime issues found. All three actionable Round-1 findings are fixed; the one outstanding item was deliberately deferred.

REVIEW_PASS
