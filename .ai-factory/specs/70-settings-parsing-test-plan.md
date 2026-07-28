# Settings Parsing & DSN — Test Plan

**Date:** 2026-07-29
**Source:** roadmap-test-coverage agent

## Source Overview

`src/core/config.py` defines `Settings` (a `pydantic-settings` `BaseSettings`) — the single operator-facing configuration surface for Herald, read from environment variables and a `.env` file. Five fields are `Annotated[..., NoDecode]`, which disables pydantic-settings' built-in JSON decoding so that four hand-written `mode="before"` validators own the string→structure translation: comma-separated org IDs (`serve_allowlist`), JSON objects (`canonical_refs`, `github_org_logins`, `telegram_channels`, `repo_apps`), a bespoke `from>to:kind` mini-grammar (`project_edges`), and a JSON array of `ReportSchedule` dataclasses (`report_schedules`). `Settings.postgres_dsn` composes the connection string handed to `create_pool` in `src/main.py`, and `get_settings()` is an `lru_cache`d process-wide singleton consumed by `src/main.py`, `src/ingestion/router.py`, and all five `scripts/*` entrypoints.

These validators are the archetypal silent-failure surface: a mis-parsed value produces a *valid-looking* `Settings` object that quietly serves the wrong orgs, posts to the wrong Telegram channel, or seeds the wrong project-graph edges — no crash, no log line.

## Instantiation

Direct construction, no fixtures needed for the validator cases:

```python
Settings(github_webhook_secret="x", telegram_bot_token="x", _env_file=None, <field>=<value>)
```

`github_webhook_secret` and `telegram_bot_token` are the only required fields; every test must pass both or get a two-error `ValidationError`.

**`_env_file=None` is mandatory in every new test in this plan.** It is missing from both existing test files, which is latent — see Gotchas. Recommend a module-local helper:

```python
def make_settings(**overrides):
    return Settings(github_webhook_secret="x", telegram_bot_token="x", _env_file=None, **overrides)
```

**What must be mocked/neutralized:**

| Dependency | How |
|---|---|
| Ambient env vars (`make test` exports all of `.env.dev` — see Gotchas) | `monkeypatch.delenv(name, raising=False)` for every `POSTGRES_*`, `SERVE_ALLOWLIST`, `GITHUB_*`, `TELEGRAM_*` key, **or** pass every field the assertion depends on as an explicit kwarg (kwargs outrank env). Explicit kwargs are the cheaper, more robust choice for validator tests; `delenv` is required only for the `postgres_dsn`-defaults and required-field tests. |
| `.env` file discovery (`env_file=".env"`, resolved relative to CWD; the file is gitignored and may exist on a dev machine) | `_env_file=None` |
| `get_settings` `lru_cache` | `get_settings.cache_clear()` **before and after** — mirror the existing `webhook_secret_env` fixture in `tests/conftest.py`, which already gets this right. Use `monkeypatch.setenv` so env is restored on teardown. |
| Postgres, Ollama, GitHub, Telegram | **Nothing.** `postgres_dsn` is pure string composition and `Settings` construction touches no network or disk beyond the env file. No I/O fakes belong in this file. |

Suggested location: `tests/core/test_config.py` (a `tests/core/` package does not yet exist — it needs an `__init__.py`, matching every other test package in the repo).

## Existing Coverage

Three assertions total, all incidental:

- `tests/changelog/test_schedule.py` — `report_schedules` JSON string → `(ReportSchedule(...),)`.
- `tests/changelog/test_schedule.py` — `report_schedules` unset and `""` → `()`.
- `tests/routing/test_role_for_branch.py` — `telegram_channels` JSON string `'{"1": "-100123"}'` → `{1: "-100123"}` (the str→int key coercion).

Everything else is unpinned: **all** of `_parse_serve_allowlist`, **all** of `_parse_project_edges`, `_parse_json_dict`'s error and falsy paths and its three other fields, `postgres_dsn` entirely, and `get_settings` caching entirely. Note both existing files construct `Settings` without `_env_file=None`.

## Test Cases

Ordering note: `_parse_json_dict` and `_parse_report_schedules` check the passthrough type **first** and truthiness **second**; `_parse_serve_allowlist` has no falsy branch at all. Several cases below exist specifically to pin that ordering.

### `_parse_serve_allowlist`

1. **should parse a comma-separated string into a frozenset of ints when given `"1,2,3"`** — the `SERVE_ALLOWLIST` env format from `.env.example`. Assert `== frozenset({1, 2, 3})` and `isinstance(..., frozenset)` (the field is the org-membership gate in `src/ingestion/router.py`; `in` against a `list` would still work, so the container type must be asserted explicitly or the regression is invisible).
2. **should strip surrounding whitespace and skip empty tokens when given `" 1 , 2 ,,"`** — verified → `frozenset({1, 2})`. Pins that a trailing comma or a space after the comma (both natural in a hand-edited `.env`) does not silently drop or corrupt an org ID.
3. **should return an empty frozenset when given `""`** — `"".split(",")` yields `[""]`, filtered by the `if token` guard. This is the shipped `.env.example` value (`SERVE_ALLOWLIST=` is blank), so it is the real cold-start path.
4. **should pass a set/frozenset through untouched and coerce its members to int when given `{"1", "2"}`** — verified → `frozenset({1, 2})`; the isinstance branch skips parsing and pydantic's `frozenset[int]` coercion does the int conversion. Non-obvious: the validator's early return does *not* mean "no conversion happens".
5. **should treat a bare int as a single-element allowlist when given `7`** — verified → `frozenset({7})` via `str(7).split(",")`. Pins that a YAML/TOML-sourced scalar int is accepted rather than exploding.
6. **should reject the whole value rather than silently dropping the bad token when given `"1,abc"`** — `pytest.raises(ValidationError)`. The silent-failure counterfactual is real: a `try/except: continue` in the loop would drop org 1's neighbour and quietly narrow the serve allowlist. This test forbids that refactor.
7. **should reject a list input when given `[1, 2]`** — verified: `str([1,2])` → `"[1, 2]"` → `int("[1")` → `ValidationError`. Non-obvious and worth pinning as a documented boundary: a `list` is the one plausible Python-literal shape the validator does *not* accept, unlike `_parse_project_edges` and `_parse_report_schedules` which both do.
8. **should reject `None` rather than defaulting to empty when given `serve_allowlist=None`** — verified: `str(None)` → `int("None")` → `ValidationError`. Pins that an explicit null does *not* fall back to the empty default (contrast with `_parse_json_dict`, case 13 below, which *does* — the asymmetry should be pinned on both sides).

### `_parse_json_dict` (`canonical_refs`, `github_org_logins`, `telegram_channels`, `repo_apps`)

9. **should coerce JSON string keys to ints for `github_org_logins` when given `'{"244165546":"mind-systems"}'`** — verified → `{244165546: "mind-systems"}`. This is the exact `.env.example` value and it feeds `clone_source` in `src/main.py`, where a str key would make every clone URL lookup miss. `telegram_channels` has this pinned already; `github_org_logins` does not. Assert `"244165546" not in settings.github_org_logins` as well — the failure mode is a dict that *looks* populated but never matches.
10. **should keep string keys as strings for `canonical_refs` when given `'{"repo-name":"main"}'`** — the `dict[str, str]` twin of case 9. Guards against someone "unifying" the four fields onto one key type; `resolve_canonical_ref` (`src/github/mirror.py`) does a `.get(repo)` by repo name.
11. **should pass a dict through and still coerce its keys when given `{"1": "a"}` for `telegram_channels`** — verified → `{1: "a"}`. Same "early return is not a no-op" point as case 4; matters because in-test construction uses dict literals while production uses env strings, and the two paths must agree.
12. **should return an empty dict when given `""`** — the blank `CANONICAL_REFS=` in `.env.example`. Without this branch `json.loads("")` would raise, so this pins the shipped-default path.
13. **should return an empty dict when given `None`** — verified → `{}` (the `if not value` branch). Contrast with case 8.
14. **should return an empty dict when given `{}`** — pins the branch *ordering*: `isinstance(value, dict)` is checked before `if not value`, so `{}` returns via the passthrough.
15. **should reject unparseable JSON when given `"notjson"`** — verified `ValidationError`. `json.JSONDecodeError` subclasses `ValueError`, which is why pydantic converts it into a field error instead of letting it escape. Non-obvious and load-bearing: it is the reason this validator's error path behaves better than `_parse_report_schedules`' (cases 32–33).
16. **should reject a JSON array when given `'["a"]'`** — verified: the validator returns a `list`, pydantic rejects with `dict_type`. Pins that a mistyped `CANONICAL_REFS=["a","b"]` fails at startup rather than becoming `{}`.
17. **should reject non-string values when given `'{"a":1}'` for `canonical_refs`** — verified `string_type` error; pydantic v2 does not coerce int→str in lax mode. An operator writing `{"repo": 1}` gets a startup failure, not a branch named `"1"`.

### `_parse_project_edges`

18. **should parse a single `from>to:kind` token when given `"mind_api>mind_mobile:CONTRACT"`** — the `.env.example` value verbatim. Assert the exact `(("mind_api", "mind_mobile", "CONTRACT"),)` tuple-of-tuples shape, which `src/main.py` destructures positionally — a shape change is silent until an `EdgeKind(kind)` blows up at startup.
19. **should upper-case the kind and strip whitespace around every part when given `" a > b : contract "`** — verified → `(("a", "b", "CONTRACT"),)`. `.env.example` documents kind as case-insensitive, and `EdgeKind` (`src/graph/models.py`) is a `StrEnum` of upper-case members, so this normalization is the only thing standing between a lower-case `.env` entry and a startup crash.
20. **should parse multiple edges and skip empty tokens when given `"a>b:CONTRACT, ,c>d:AUTH"`** — verified → both triples, blank token dropped.
21. **should return an empty tuple when given `""` / `None` / `()`** — three asserts; `""` is the shipped `.env.example` default.
22. **should NOT normalize the kind when given a pre-built list of triples `[("a","b","contract")]`** — verified → `(("a", "b", "contract"),)`, kind left lower-case. **This is the sharpest silent divergence in the file:** the same logical config reaches `EdgeKind("contract")` and raises `ValueError` on the Python-literal path while working fine on the string path. Write the test to pin *current* behavior; do not fix it here.
23. **should reject a token missing `>` when given `"ab:CONTRACT"`** — verified: the explicit `malformed PROJECT_EDGES token` message. Assert on the message text — it is the operator's only debugging affordance and is worth pinning as contract.
24. **should reject a token missing `:` when given `"a>b"`** — the other half of the `or` in the guard.
25. **should produce an unhelpful unpack error when the separators are inverted, e.g. `"a:b>c"`** — verified: the guard passes (both characters present), then `rest.split(":", 1)` returns one element and tuple-unpacking raises `not enough values to unpack`. The guard checks for *presence*, not *order*. Pin it as a known gap.
26. **should accept an unknown kind without complaint when given `"a>b:bogus"`** — verified → `(("a", "b", "BOGUS"),)`. The validator does not know about `EdgeKind`; the failure is deferred to `EdgeKind(kind)` inside the lifespan in `src/main.py`, i.e. at startup, after the pool is already open. (Related: `"a>b>c:AUTH"` → `("a", "b>c", "AUTH")` — an extra `>` silently becomes part of the repo name. Fold in as a second assert.)

### `_parse_report_schedules`

27. **should parse a JSON array of schedule objects when given the `.env.example` two-schedule value** — extend beyond the existing single-schedule test to the actual shipped `REPORT_SCHEDULES` string (daily + weekly), asserting both entries and their order. `deploy/report-crons.crontab` selects by `name`, so name fidelity is operationally load-bearing.
28. **should coerce a string window to an int when given `'[{"name":"d","window":"7","sections":["s"]}]'`** — verified → `window=7` via the explicit `int(...)`. Silent-failure guard: `ReportSchedule` is a plain frozen dataclass with **no runtime type enforcement**, so without that `int()` call a string window would sail through and only surface as a `TypeError` deep inside `timedelta(days=...)`.
29. **should split a string `sections` value into per-character entries when given `"sections":"summary"`** — verified → `sections=('s','u','m','m','a','r','y')`. **The single worst silent failure in the module:** `tuple("summary")` is not an error, so a plausible typo yields a schedule with seven bogus section keys that fails much later with a `ValueError` naming a single letter. Pin current behavior and file it as a defect candidate — not owned by any existing roadmap task.
30. **should pass a tuple/list of `ReportSchedule` instances through when given `(ReportSchedule(...),)`** — the `all(isinstance(...))` branch; this is the shape tests build directly.
31. **should return an empty tuple when given `[]`** — verified → `()`. Non-obvious: `all()` over an empty list is `True`, so `[]` exits via the *passthrough* branch, never reaching `json.loads`.
32. **should raise `TypeError`, not `ValidationError`, when given a list of plain dicts** — verified: `all(isinstance(..., ReportSchedule))` is `False`, so control falls to `json.loads(list)` → `TypeError`. **This escapes pydantic's error machinery entirely** (pydantic v2 converts only `ValueError`/`AssertionError`). A list of dicts is exactly what a YAML/TOML config loader or a test author would hand in. Pin with `pytest.raises(TypeError)` and flag as a defect candidate.
33. **should raise `KeyError`, not `ValidationError`, when a schedule object omits `sections`** — verified: bare `KeyError: 'sections'` escapes for the same reason. Same for a JSON *object* instead of an array (`'{"name":"d"}'` → `TypeError: string indices must be integers`).
34. **should compare equal and hash when two `ReportSchedule`s carry the same values** — verified frozen + hashable + value-equal, and mutation raises `FrozenInstanceError`. Cheap, and it is the assumption every `==` assertion in `tests/changelog/test_schedule.py` silently rests on.

### `postgres_dsn`

> **Overlap with roadmap task 19.2 (`.ai-factory/specs/57-postgres-dsn-encoding.md`) — read before writing these.** That spec owns percent-encoding `postgres_user`/`postgres_password` in `Settings.postgres_dsn` *and* in the three mirrored fixture helpers (`tests/episodic/conftest.py`, `tests/graph/conftest.py`, `tests/knowledge/conftest.py`). **Do not write a test asserting the raw unencoded output for a credential containing a reserved character.** Case 35 below is deliberately written to be the *invariant* half of 19.2's own guard ("credentials with no reserved character produce a byte-identical DSN"), so it survives the fix unchanged and becomes 19.2's regression net. Cases 36–37 exercise only the host/port/db components, which 19.2 leaves untouched.

35. **should compose the default DSN byte-for-byte when no postgres fields are overridden** — expect exactly `postgresql://herald_username:herald_password@localhost:5432/herald_database` (verified). **Requires `monkeypatch.delenv` for all five `POSTGRES_*` keys** — `make test` exports `.env.dev`, which sets every one of them, so without the delenv this test passes on CI and fails on the author's machine (or vice versa). Annotate it in the source.
36. **should interpolate every component in order when all five postgres fields are overridden** — distinct sentinel values per component (`u1`/`p1`/`h1`/`1234`/`d1`) so a transposed user/password or host/db is visible. Positional-swap bugs in an f-string are the definition of a silent failure.
37. **should render an int port with no quoting when `postgres_port` is supplied as the string `"6543"`** — verified: pydantic coerces to `int`, so the DSN contains `:6543/`. Env vars are always strings, making this the production path for a non-default port.

### `get_settings` caching

38. **should return the identical object on repeated calls** — verified `get_settings() is get_settings()`.
39. **should keep serving the first-seen values after the environment changes** — verified: set `SERVE_ALLOWLIST=1,2`, call `get_settings()`, then set `SERVE_ALLOWLIST=9` and observe `frozenset({1, 2})` still returned. Pins the cache as *intended* behavior and documents the trap that makes every other env-dependent test order-dependent.
40. **should observe the new environment after `cache_clear()`** — verified. This is the contract the `webhook_secret_env` fixture depends on; nothing currently asserts it holds.
41. **should read `SERVE_ALLOWLIST` / `TELEGRAM_CHANNELS` / `PROJECT_EDGES` through the env-var path, not just constructor kwargs** — verified end-to-end via `monkeypatch.setenv` + `cache_clear()`. **This is the only test that actually exercises `NoDecode`.** Without that annotation, pydantic-settings would JSON-decode these env values *before* the validators run, and `SERVE_ALLOWLIST=1,2` would fail outright. Every other test in this plan passes Python objects or strings as constructor kwargs, which bypasses the settings decoder entirely — so if someone drops `NoDecode`, cases 1–33 all still pass and only production breaks.

## Gotchas

- **`make test` exports `.env.dev` into the test process.** The `Makefile` is `-include .env.dev` + `export`, so `POSTGRES_*`, `SERVE_ALLOWLIST`, `GITHUB_WEBHOOK_SECRET`, `GITHUB_APP_ID`, `SSH_*`, and `OLLAMA_*` are all live env vars during `uv run pytest`. Precedence is **constructor kwargs > env vars > `.env` file > field defaults**, so any test asserting a *default* is passing only because `.env.dev` happens not to set that key today. Always `monkeypatch.delenv(..., raising=False)` for any key whose *absence* an assertion depends on.
- **`_env_file=None` should be on every `Settings(...)` in tests.** `model_config` sets `env_file=".env"`, resolved relative to CWD. `.env` is gitignored, does not exist in this checkout, and is a `.env.example` copy away from existing — at which point tests start reading a developer's personal config. Neither existing test file passes it; adding it there is a cheap hardening win.
- **`lru_cache` on `get_settings` makes env-dependent tests order-dependent.** Clear **before and after** — the `webhook_secret_env` fixture in `tests/conftest.py` is the pattern to copy. Note `lru_cache` does not cache exceptions, so a failed `Settings()` construction leaves no poisoned entry.
- **pydantic converts only `ValueError` and `AssertionError` into field errors.** `_parse_serve_allowlist`'s `int()`, `_parse_project_edges`' explicit `raise`, and `_parse_json_dict`'s `json.JSONDecodeError` all become clean `ValidationError`s. `_parse_report_schedules` is the outlier: its `TypeError` and `KeyError` escape raw. A test written the intuitive way will fail and mislead the next reader into "fixing" the wrong thing.
- **Validator branch ordering differs per validator and is load-bearing.** Cases 8, 13, 14, and 31 exist specifically to freeze this.
- **str-vs-int dict keys.** `github_org_logins` and `telegram_channels` are `dict[int, str]`; `canonical_refs` and `repo_apps` are `dict[str, str]` — all four share one validator. Assert both the positive (`244165546 in d`) and the negative (`"244165546" not in d`); a regression here yields a fully-populated dict where every lookup misses.
- **`frozenset` semantics.** `serve_allowlist` is a `frozenset[int]` and the `in` checks would work identically against a `list` or `set`, so type regressions are invisible to behavior-only assertions. Assert the container type explicitly.
- **`ReportSchedule` is a plain frozen dataclass, not a pydantic model.** It performs no runtime type validation of its own; the only coercion is the explicit `int(o["window"])` and `tuple(o["sections"])` inside the validator. Anything bypassing that validator gets zero checking — which is exactly how case 29's per-character `sections` tuple can exist.
- **`Literal` and required fields fail loudly and need no dedicated tests.** `version_increment="huge"` → clean `literal_error`; missing required fields → clean `ValidationError`. Skip both. Likewise `extra="ignore"`.
