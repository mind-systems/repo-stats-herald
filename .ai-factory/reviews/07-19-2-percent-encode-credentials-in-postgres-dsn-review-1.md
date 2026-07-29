## Code Review — 19.2 Percent-encode credentials in `postgres_dsn`

**Scope:** `src/core/config.py` + four test conftests (`tests/episodic`, `tests/graph`, `tests/knowledge`, `tests/ingestion`). Plan tasks 1–5 all marked `[x]`.

### What the change does
Wraps `postgres_user` / `postgres_password` in `urllib.parse.quote(value, safe="")` before interpolating them into the `postgresql://user:password@host:port/db` DSN, in the production property and each of the four byte-identical `_dsn()` fixture mirrors. Host, port, and db are left untouched.

### Correctness checks

- **All construction sites covered.** An independent `grep -rn "postgresql://"` across `src/`, `tests/`, `scripts/` returns exactly five sites — the `postgres_dsn` property (`src/core/config.py:112`) and the four `_dsn()` helpers — and every one is encoded. No production caller builds its own DSN: `src/main.py:50` and the `scripts/*` entrypoints all route through `settings.postgres_dsn`, so Task 1 covers the entire production surface.
- **`safe=""` is the right choice.** The default `quote` `safe="/"` would leave a `/` in a password unescaped, mis-parsing the authority; `safe=""` escapes `/` along with `@ : # ?`. Unreserved characters (`A-Za-z0-9_.-~`) are left alone, which is valid in RFC 3986 userinfo.
- **Encode/decode is symmetric.** asyncpg percent-decodes the userinfo when parsing a DSN, so an encoded credential round-trips back to the original secret at connect time. Encode-on-build / decode-on-parse is balanced — no double-encoding and no residual escapes reaching the server.
- **No existing environment changes.** `herald_username` / `herald_password` (defaults) and the `u1` / `p1` overrides contain no characters `quote(safe="")` escapes, so the guard tests in `tests/core/test_config.py:261–281` (byte-for-byte default DSN, ordered-override interpolation, string-port) pass unchanged. The "no connection string changes for existing environments" guard holds.
- **Scope is tight.** Encoding is confined to the two credential components; host/port/db are untouched, matching how a DSN authority is parsed. Imports added are stdlib (`from urllib.parse import quote`) — no new dependency, no convention violation.

### Runtime-break review
No migrations, schema, or type surfaces are touched. The property signature is unchanged (`-> str`). No race conditions or ordering concerns — this is a pure string transformation at DSN-build time. Nothing to break at runtime.

### Findings
None. The implementation matches the plan exactly across all five sites, the API choice is correct, and the round-trip through asyncpg is sound.

REVIEW_PASS
