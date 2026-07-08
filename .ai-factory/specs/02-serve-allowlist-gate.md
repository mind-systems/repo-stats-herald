# 2.2 — Serve-allowlist gate

**Phase:** 2 — Ingestion & the event stream. Depends on 2.1 (needs the parsed `PushEvent`).

## Current state

After task 2.1, a verified `push` is parsed into a `PushEvent` for **any** organization that installed the App. Herald must act only on organizations it serves (see `docs/spec/ingestion.md` "Who Herald serves"). The list of served org ids is in `.env.dev` (`SERVE_ALLOWLIST=244165546`) but `Settings` does not read it, and nothing checks it.

## Change

Gate the verified push on a serve-allowlist of GitHub org ids before any downstream work.

- Extend `src/core/config.py` `Settings` with `serve_allowlist` — read `SERVE_ALLOWLIST` (comma-separated org ids) and expose it as a `frozenset[int]` (a `field_validator`/property that splits on `,`, strips, and parses to `int`; empty string → empty set).
- In `src/ingestion/router.py`, after parsing `PushEvent` (2.1): if `push.org_id not in settings.serve_allowlist` → drop (log at info: org id + repo, "not served"), return `204`; otherwise continue.
- The check runs before anything expensive (no token minting, no processing) — the drop is cheap.

## Files & types

- edit `src/core/config.py` (`Settings.serve_allowlist: frozenset[int]`)
- edit `src/ingestion/router.py` (allowlist check after parse)

## Guards

- **Fail-closed:** an empty allowlist serves no one (never default to "serve all").
- Drop is silent and cheap: no installation token, no summarization, no delivery — just a log line and `204`.
- Org id compared as `int` (the payload's numeric id, rename-proof), not the login string.
- The allowlist is read through `Settings`, not from env inline.

## Verification

- A verified push whose `org_id` is `244165546` proceeds past the gate.
- A verified push whose `org_id` is not listed → `204`, logged as not-served, and nothing downstream runs.
- With `SERVE_ALLOWLIST` empty → every push is dropped (fail-closed).
