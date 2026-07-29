## Plan Review Summary

**Plan:** 19.2 — Percent-encode credentials in `postgres_dsn`
**Files Targeted:** 4 (1 production + 3 test fixtures)
**Risk Level:** 🟡 Medium

### Context Gates
- **Architecture** (`.ai-factory/ARCHITECTURE.md`): OK — the change is confined to `src/core/config.py` (cross-cutting infra) and test conftests. Config is read once at the composition root and injected; the DSN property stays where it belongs. No boundary or dependency-direction concern. WARN: none.
- **Rules** (`.ai-factory/RULES.md`): OK — no convention violation introduced. Secrets stay in env; the property still composes from `Settings` primitives.
- **Roadmap** (`.ai-factory/ROADMAP.md`): Plan heading `19.2` matches a roadmap task line; linkage present. No missing linkage.
- **Skill-context** (`.ai-factory/skill-context/aif-review/SKILL.md`): absent — no project-specific overrides to apply.

### Critical Issues

**A fourth identical `_dsn()` mirror is missed: `tests/ingestion/conftest.py`.**
The plan's Context states the defect "lives in one production path and **three** test-fixture mirrors and all four move together as one concern," and Tasks 2–4 target `tests/episodic`, `tests/graph`, and `tests/knowledge`. But a fifth file carries the exact same helper:

```
tests/ingestion/conftest.py:23-29   def _dsn() -> str: ... f"postgresql://{user}:{password}@{host}:{port}/{db}"
tests/ingestion/conftest.py:303      pool = await create_pool(_dsn())
```

This helper is byte-for-byte identical to the three the plan does cover, and it likewise builds its own pool via `create_pool(_dsn())`. By the plan's own stated rationale (Task 2: "its DSN must match the production path's encoding to stay in step"), this mirror must move with the others. Leaving it out breaks the "all move together" invariant the plan sets for itself. **Add a Task 5** encoding `user`/`password` with `urllib.parse.quote(value, safe="")` in `tests/ingestion/conftest.py`, adding the `from urllib.parse import quote` import — identical in shape to Tasks 2–4.

(Grep basis: `_dsn()` helpers exist in exactly four conftests — episodic, graph, knowledge, ingestion; `postgres_dsn` is the production property. The plan covers four of the five sites.)

### Non-blocking Notes

- **Line references verified.** `postgres_dsn` property at `src/core/config.py:106-111` ✓; episodic `_dsn` at `22-28` ✓; graph `_dsn` at `15-21` ✓; knowledge `_dsn` at `16-22` ✓. Import-anchor note ("alongside `json`/`dataclasses`/`functools`") matches `config.py:1-3`.
- **API choice is correct.** `quote(value, safe="")` encodes `/` as well as `@ : # ?` (the default `safe="/"` would leave `/` un-escaped in a password), and asyncpg unquotes userinfo when parsing the DSN — so the encoded value round-trips to the original credential. The fix direction is sound.
- **Byte-identical-for-defaults guard holds.** `herald_username` / `herald_password` contain no characters `quote` escapes, so `tests/core/test_config.py:261-281` (`test_should_compose_default_dsn_byte_for_byte`, the `u1/p1` interpolation test, the string-port test) continue to pass unchanged. The plan's stated guard is accurate.
- **Settings — Testing: no.** No new test is asked for. Consistent with the "no observable behavior change for existing environments" framing; the fix is only reachable by credentials with reserved characters, which no current fixture exercises. Acceptable, given the guard tests above already pin the default/override composition.

### Positive Notes
- Correctly scopes encoding to `user`/`password` only, leaving `host`/`port`/`db` untouched — matches how a DSN's authority is actually parsed.
- Keeps the production path and its test-fixture mirrors in lockstep, which is the right instinct — the only flaw is that the mirror inventory is one short.
- Explicitly reasons about the no-change-for-defaults guard rather than assuming it.

Resolve the missing `tests/ingestion/conftest.py` mirror (add Task 5) and the plan is complete and correct.
