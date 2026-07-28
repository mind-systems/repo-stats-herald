# 19.2 — Percent-encode credentials in `postgres_dsn`

**Phase:** 19 — Boundary representation mismatches. Independent of 19.1, 19.3, and 19.4 — touches only DSN composition.

## Current state

`Settings.postgres_dsn` interpolates `postgres_user` and `postgres_password` into a URL with no encoding. This is the production path: `src/main.py` hands the resulting DSN to `create_pool`, so a password holding `@`, `:`, `/`, `#`, or `?` produces a DSN that either addresses the wrong host or fails to parse outright. The identical unescaped construction is mirrored in three test fixtures — `tests/episodic/conftest.py:28`, `tests/graph/conftest.py:21`, and `tests/knowledge/conftest.py:22` — each building its own DSN the same unencoded way for its own pool.

## Change

Percent-encode both credential fields before interpolating them into the DSN, in `Settings.postgres_dsn` and in each of the three fixture helpers. All four constructions move together: they are one concern — the same latent defect restated four times — not four separate tasks.

## Files & types

- edit `src/core/config.py` (`Settings.postgres_dsn`)
- edit `tests/episodic/conftest.py` (the DSN-building helper)
- edit `tests/graph/conftest.py` (the DSN-building helper)
- edit `tests/knowledge/conftest.py` (the DSN-building helper)

## Guards

- Credentials containing no URL-reserved character produce a byte-identical DSN to today's output, so no existing environment's connection string changes.
- Only the user and password components are encoded — host, port, and database name are untouched.
- All three fixture mirrors are updated alongside the production path in the same change, so none of them silently diverges from it.

## Verification

- A `postgres_password` containing a reserved character round-trips correctly through a URL parse and connects successfully.
- Today's dev-default credentials yield exactly the DSN string they yield before this change.
- Each of the three test fixtures connects successfully with a credential containing a reserved character, matching the production path's behavior.
