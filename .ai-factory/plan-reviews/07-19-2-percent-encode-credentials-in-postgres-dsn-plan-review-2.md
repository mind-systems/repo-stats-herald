## Plan Review Summary

**Plan:** 19.2 — Percent-encode credentials in `postgres_dsn`
**Files Targeted:** 5 (1 production + 4 test fixtures)
**Risk Level:** 🟢 Low

### Context Gates
- **Architecture** (`.ai-factory/ARCHITECTURE.md`): OK — the change stays in `src/core/config.py` (cross-cutting infra, where the DSN property belongs) plus four test conftests. Config is still read once at the composition root and injected; no boundary or dependency-direction concern. WARN: none.
- **Rules** (`.ai-factory/RULES.md`): OK — no convention violation. Secrets stay in env; the property still composes only from `Settings` primitives. `quote` is a stdlib import.
- **Roadmap** (`.ai-factory/ROADMAP.md`): Plan heading `19.2` matches its roadmap task line; linkage present.
- **Skill-context** (`.ai-factory/skill-context/aif-review/SKILL.md`): absent — no project-specific overrides.

### Critical Issues
None. The one critical issue from plan-review-1 — the missed `tests/ingestion/conftest.py` mirror — is resolved: the Context now enumerates all four fixture mirrors (`tests/episodic`, `tests/graph`, `tests/knowledge`, `tests/ingestion`) and **Task 5** encodes the ingestion helper identically to the others.

### Verification (ground-truth checks against the code)
- **All five DSN sites are covered.** Grep confirms exactly five construction points: the `postgres_dsn` property and four byte-identical `_dsn()` conftest helpers. Every production caller (`src/main.py:50`, `scripts/report.py:55`, `scripts/backfill_episodic.py:41`, `scripts/backfill.py:40`, `scripts/eval.py:215`) routes through `settings.postgres_dsn`, so Task 1 alone covers the entire production surface; the four fixtures are the only independent mirrors and each gets its own task.
- **Line references are accurate.** `postgres_dsn` property at `src/core/config.py:106–111` ✓; episodic `_dsn` at `22–28` ✓; graph `_dsn` at `15–21` ✓; knowledge `_dsn` at `16–22` ✓; ingestion `_dsn` at `23–29` with its pool built at `303` ✓. Import-anchor note ("alongside the existing `json`/`dataclasses`/`functools` imports") matches `config.py:1–3`.
- **API choice is correct.** `quote(value, safe="")` escapes `/` in addition to `@ : # ?` (the default `safe="/"` would leave a `/` in a password unescaped and mis-parse the authority). asyncpg percent-decodes the userinfo when parsing the DSN, so the encoded value round-trips to the original credential — encode-on-build / decode-on-parse is symmetric.
- **No existing test breaks.** `herald_username` / `herald_password`, and the override credentials `u1` / `p1`, contain no characters `quote(safe="")` escapes, so `tests/core/test_config.py:261–281` (byte-for-byte default DSN, ordered-override interpolation, string-port) continue to pass unchanged. The plan's "no environment's connection string changes" guard holds.
- **Scope is right.** Encoding is confined to `user`/`password`; `host`/`port`/`db` stay untouched, matching how a DSN's authority is parsed.

### Positive Notes
- Keeps the production path and its four fixture mirrors in strict lockstep — the correct instinct for a defect that is duplicated verbatim across files, and the mirror inventory is now complete.
- Explicitly reasons about the no-change-for-defaults guard rather than assuming it, and correctly justifies `safe=""` over the default.
- Each task names its exact file, line span, and import addition — unambiguous for the implementer.

## Deferred observations
- Affects: this task's `Settings: Testing: no` — the plan adds no test exercising the new behavior (a credential containing a reserved character such as `@` producing an encoded, still-parseable DSN). The existing guard tests only pin that defaults/overloads are unchanged, so the encoding path itself stays unproven. This is consistent with the task's declared `Testing: no` setting and the "latent defect, no current fixture exercises reserved-char credentials" framing, so it is not a finding against the plan as scoped; a future hardening pass could add a single `postgres_password="p@ss/w:rd"` assertion cheaply.

PLAN_REVIEW_PASS
