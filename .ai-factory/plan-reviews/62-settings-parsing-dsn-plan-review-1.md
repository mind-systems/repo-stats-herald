## Code Review Summary

**Files Reviewed:** 1 plan (`.ai-factory/plans/62-settings-parsing-dsn.md`) against `src/core/config.py`, `tests/conftest.py`, `Makefile`, `.env.example`, `pyproject.toml`, and the governing spec `.ai-factory/specs/70-settings-parsing-test-plan.md`
**Risk Level:** 🟢 Low

This is a **test plan** — it pins current behavior of `Settings`, its four `mode="before"` validators, `postgres_dsn`, `get_settings` caching, and the `NoDecode` env path. It explicitly (and correctly) does not touch source, and pins several defect candidates as *current* behavior rather than fixing them.

### Context Gates

- **Architecture (ARCHITECTURE.md):** PASS — the plan adds only `tests/core/test_config.py` + `tests/core/__init__.py`, touching no module boundary or dependency rule. `src/core/config.py` is the cross-cutting infra surface it exercises; no feature-to-feature coupling introduced.
- **Rules (RULES.md):** PASS — file is intentionally empty (no project counter-defaults); nothing to violate.
- **Roadmap (ROADMAP_TESTS.md):** PASS — linkage confirmed. The `Settings parsing & DSN` line names `Spec: .ai-factory/specs/70-settings-parsing-test-plan.md`, and the plan is a faithful realization of it. Every guard in the contract line (`_env_file=None` everywhere, raw `TypeError`/`KeyError` caught as themselves, DSN default asserted in its byte-identical no-reserved-character form that survives task 19.2) is carried into the plan's setup notes and tasks.

### Spec-coverage cross-check

All 41 cases of spec 70 are represented across the 14 tasks, with none dropped:
- `_parse_serve_allowlist` (spec 1–8) → Tasks 1–2
- `_parse_json_dict` (spec 9–17) → Tasks 3–5
- `_parse_project_edges` (spec 18–26) → Tasks 6–8
- `_parse_report_schedules` (spec 27–34) → Tasks 9–11
- `postgres_dsn` (spec 35–37) → Task 12
- `get_settings` / `NoDecode` (spec 38–41) → Tasks 13–14

### Behavioral verification against source

Every non-obvious assertion in the plan was traced through `src/core/config.py` and holds:
- Task 1/4 set-passthrough: `_parse_serve_allowlist` returns `{"1","2"}` unchanged, then `frozenset[int]` coercion yields `{1,2}` — correct.
- Task 2 `[1,2]` rejection: `str([1,2])` → `int("[1")` raises → `ValidationError` — correct.
- Task 4/5 branch ordering: `isinstance(value, dict)` before `if not value`, so `{}` passes through and `""`/`None` return `{}` — correct.
- Task 7 literal-path divergence: `[("a","b","contract")]` is returned via `tuple(value)` with no upper-casing — correct pin of the silent divergence.
- Task 7 `"a>b>c:AUTH"`: `split(">",1)`/`split(":",1)` folds the extra `>` into `"b>c"` — correct.
- Task 8 inverted `"a:b>c"`: guard passes (both chars present), `rest.split(":",1)` yields one element, unpack raises → `ValidationError` — correct.
- Task 9 empty `[]`: `all()` over empty is `True`, exits via passthrough before `json.loads` — correct.
- Task 10 raw escapes: list-of-dicts → `json.loads(list)` `TypeError`; missing `sections` → `KeyError`; JSON object → key-iteration `o["name"]` `TypeError` — all correct, and correctly caught as themselves (not `ValidationError`), matching the pydantic "only `ValueError`/`AssertionError` convert" rule.
- Task 12 DSN: default composes byte-for-byte to `postgresql://herald_username:herald_password@localhost:5432/herald_database`; sentinels and the string-`"6543"`→int-port case use no reserved characters, so they survive task 19.2's percent-encoding fix unchanged — correct, and consistent with spec 70's explicit overlap warning.
- Task 14 `NoDecode`: only env-path test; without the annotation `SERVE_ALLOWLIST=1,2` would be JSON-decoded before the validator and fail — correct rationale.

### External-assumption verification

- `Makefile` is `-include .env.dev` + `export` → `make test` does export `.env.dev` into the process, so the plan's mandate to `delenv` for default assertions and pass `_env_file=None` for validator kwargs is justified and necessary. ✓
- `.env.example` matches every value the plan cites: blank `SERVE_ALLOWLIST`/`CANONICAL_REFS`/`GITHUB_ORG_LOGINS`/`PROJECT_EDGES` (cold-start defaults) and the exact two-schedule `REPORT_SCHEDULES` (daily window 1 / weekly window 7). Task 9's "two-schedule .env.example value" resolves. ✓
- `tests/core/` genuinely does not exist; sibling packages (`tests/commits/`, `tests/github/`) each carry `__init__.py`, so the plan's setup instruction is accurate. ✓
- `pyproject.toml`: `testpaths=["tests"]`, `pythonpath=["."]`, `asyncio_mode="auto"` — the module-under-test test command `uv run pytest tests/core/test_config.py` is valid. ✓
- The `make_settings` helper, `_env_file=None`, and the "mirror `webhook_secret_env` (clear cache before + after, drive env via `monkeypatch.setenv`)" instruction are correct against `tests/conftest.py`.

### Critical Issues

None. The plan is internally consistent, grounded in the actual source, complete against its governing spec, and uses correct pydantic-settings / pytest / `monkeypatch` / `lru_cache` API idioms. No missing migrations (test-only task), no security exposure, no wrong file paths.

### Positive Notes

- The plan correctly separates "pin current behavior" defect candidates (lower-case kind on the literal path, per-character `sections`, raw `TypeError`/`KeyError`) from fixes, keeping the test task from silently changing production behavior.
- Container-type and negative-key assertions (`isinstance(frozenset)`, `"244165546" not in d`) are called out explicitly — these are exactly the regressions a behavior-only assertion would miss.
- The DSN default case is deliberately scoped to survive roadmap task 19.2's percent-encoding change, avoiding a cross-task collision.
- The `NoDecode` env-path test (Task 14) is preserved as the single guard that would catch a dropped annotation — a real gap the kwargs-based tests cannot cover.

## Deferred observations
- Affects: `.ai-factory/specs/70-settings-parsing-test-plan.md` — the spec's Source Overview prose states "Five fields are `Annotated[..., NoDecode]`" but then enumerates seven (`serve_allowlist`, `canonical_refs`, `github_org_logins`, `telegram_channels`, `repo_apps`, `project_edges`, `report_schedules`), which matches the seven `NoDecode` fields in `src/core/config.py`. The plan under review does not restate the count, so no test is affected; this is a cosmetic miscount in the governing spec's narrative, outside this plan's file boundary.

PLAN_REVIEW_PASS
