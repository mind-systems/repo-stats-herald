# Test Plan: Settings parsing & DSN

## Context
`src/core/config.py`'s four hand-written `mode="before"` validators and the `postgres_dsn` property are a silent-failure surface: a mis-parsed value yields a valid-looking `Settings` that serves the wrong orgs, posts to the wrong chat, or seeds the wrong graph edges — no crash, no log line. These tests pin the allowlist parser, the shared JSON-dict/key-coercion validator across all four dict fields, the `from>to:kind` edge grammar, the report-schedule parser, DSN composition, and `get_settings` caching.

## Settings
- Testing: yes
- Logging: minimal
- Docs: no

## Test Command
`uv run pytest tests/core/test_config.py`

## Target Spec File
`tests/core/test_config.py`

## Setup notes for the implementer (not tasks)
- `tests/core/` does not exist yet — add `tests/core/__init__.py` (empty), matching every other test package in the repo.
- Add a module-local helper so `_env_file=None` and the two required fields are never forgotten:
  ```python
  def make_settings(**overrides):
      return Settings(github_webhook_secret="x", telegram_bot_token="x", _env_file=None, **overrides)
  ```
  `_env_file=None` is **mandatory** on every construction (validator cases pass fields as kwargs, which outrank env; only the DSN-defaults and caching groups need `monkeypatch.delenv`/`setenv`).
- For any test asserting a **default**, `monkeypatch.delenv(..., raising=False)` the relevant `POSTGRES_*` / `SERVE_ALLOWLIST` / `GITHUB_*` / `TELEGRAM_*` keys — `make test` exports `.env.dev` into the process, so an un-cleared key makes the assertion machine-dependent.
- The `get_settings` caching group must `get_settings.cache_clear()` **before and after** (mirror the `webhook_secret_env` fixture in `tests/conftest.py`) and drive env via `monkeypatch.setenv`.
- `_parse_report_schedules` raises raw `TypeError`/`KeyError` that escape pydantic — catch them as themselves, **not** as `ValidationError`.
- Pin **current** behavior wherever the spec flags a defect candidate (cases for lower-case kind on the literal path, per-character `sections`, the raw `TypeError`/`KeyError`); do not "fix" the source here.

## Tasks

### Phase 1: `_parse_serve_allowlist` — comma-separated org allowlist

- [x] **Task 1: serve_allowlist parsing and container type**
  Files: `tests/core/test_config.py`
  Test cases:
  - `should parse a comma-separated string into a frozenset of ints when given "1,2,3"` — assert `== frozenset({1, 2, 3})` and `isinstance(..., frozenset)` (the container type must be asserted explicitly; `in` against a list would still pass).
  - `should strip surrounding whitespace and skip empty tokens when given " 1 , 2 ,,"` — assert `== frozenset({1, 2})`.
  - `should return an empty frozenset when given ""` — the shipped blank `.env.example` cold-start value.
  - `should pass a set/frozenset through untouched and coerce its members to int when given {"1", "2"}` — assert `== frozenset({1, 2})`; the isinstance early-return still leaves pydantic's `frozenset[int]` coercion to convert.
  - `should treat a bare int as a single-element allowlist when given 7` — assert `== frozenset({7})`.

- [x] **Task 2: serve_allowlist rejection paths**
  Files: `tests/core/test_config.py`
  Test cases:
  - `should reject the whole value rather than silently dropping the bad token when given "1,abc"` — `pytest.raises(ValidationError)` (forbids a per-token try/except that would narrow the allowlist).
  - `should reject a list input when given [1, 2]` — `pytest.raises(ValidationError)` (`str([1,2])` → `int("[1")` fails; documents that a list is the one literal shape this validator rejects).
  - `should reject None rather than defaulting to empty when given serve_allowlist=None` — `pytest.raises(ValidationError)`; contrast with the json-dict None case.

### Phase 2: `_parse_json_dict` — the four dict fields, key coercion and ordering

- [x] **Task 3: dict key coercion and str-key preservation**
  Files: `tests/core/test_config.py`
  Test cases:
  - `should coerce JSON string keys to ints for github_org_logins when given '{"244165546":"mind-systems"}'` — assert `244165546 in d` **and** `"244165546" not in d` (a dict that looks populated but never matches is the failure mode).
  - `should keep string keys as strings for canonical_refs when given '{"repo-name":"main"}'` — assert `"repo-name" in d` with a str key (the `dict[str, str]` twin).
  - `should pass a dict through and still coerce its keys when given {"1": "a"} for telegram_channels` — assert `== {1: "a"}` (early return is not a no-op).

- [x] **Task 4: dict falsy/ordering branches**
  Files: `tests/core/test_config.py`
  Test cases:
  - `should return an empty dict when given ""` — the blank `.env.example` default (raw `json.loads("")` would raise).
  - `should return an empty dict when given None` — the `if not value` branch; contrast with Task 2's None case.
  - `should return an empty dict when given {}` — pins that `isinstance(value, dict)` is checked before `if not value`, so `{}` returns via passthrough.

- [x] **Task 5: dict rejection paths**
  Files: `tests/core/test_config.py`
  Test cases:
  - `should reject unparseable JSON when given "notjson"` — `pytest.raises(ValidationError)` (`JSONDecodeError` subclasses `ValueError`, so pydantic converts it).
  - `should reject a JSON array when given '["a"]'` — `pytest.raises(ValidationError)` (`dict_type`; a mistyped array fails at startup, not silently becomes `{}`).
  - `should reject non-string values when given '{"a":1}' for canonical_refs` — `pytest.raises(ValidationError)` (`string_type`; pydantic v2 does not coerce int→str in lax mode).

### Phase 3: `_parse_project_edges` — the `from>to:kind` grammar

- [x] **Task 6: edge parsing and normalization**
  Files: `tests/core/test_config.py`
  Test cases:
  - `should parse a single from>to:kind token when given "mind_api>mind_mobile:CONTRACT"` — assert the exact `(("mind_api", "mind_mobile", "CONTRACT"),)` tuple-of-tuples shape.
  - `should upper-case the kind and strip whitespace around every part when given " a > b : contract "` — assert `== (("a", "b", "CONTRACT"),)`.
  - `should parse multiple edges and skip empty tokens when given "a>b:CONTRACT, ,c>d:AUTH"` — assert both triples, blank token dropped.
  - `should return an empty tuple when given "" / None / ()` — three asserts, all `== ()`.

- [x] **Task 7: edge literal-path divergence and unknown kind (pin current behavior)**
  Files: `tests/core/test_config.py`
  Test cases:
  - `should NOT normalize the kind when given a pre-built list of triples [("a","b","contract")]` — assert `== (("a", "b", "contract"),)`, kind left lower-case; pin the silent divergence from the string path, do not fix.
  - `should accept an unknown kind without complaint when given "a>b:bogus"` — assert `== (("a", "b", "BOGUS"),)` (validation deferred to `EdgeKind` at startup).
  - `should fold an extra > into the repo name when given "a>b>c:AUTH"` — assert `== (("a", "b>c", "AUTH"),)`.

- [x] **Task 8: edge malformed-token rejection**
  Files: `tests/core/test_config.py`
  Test cases:
  - `should reject a token missing > when given "ab:CONTRACT"` — `pytest.raises(ValidationError, match="malformed PROJECT_EDGES token")` (assert the message text as contract).
  - `should reject a token missing : when given "a>b"` — `pytest.raises(ValidationError)` (the other half of the guard's `or`).
  - `should produce an unpack error when the separators are inverted when given "a:b>c"` — `pytest.raises(ValidationError)`; the guard checks presence not order, so unpacking raises. Pin as a known gap.

### Phase 4: `_parse_report_schedules` — JSON array of ReportSchedule

- [x] **Task 9: report-schedule parsing and coercion**
  Files: `tests/core/test_config.py`
  Test cases:
  - `should parse a JSON array of schedule objects when given the two-schedule .env.example value` — assert both entries and their order (daily + weekly; name fidelity is load-bearing for cron selection).
  - `should coerce a string window to an int when given '[{"name":"d","window":"7","sections":["s"]}]'` — assert `window == 7` and `isinstance(window, int)`.
  - `should split a string sections value into per-character entries when given "sections":"summary"` — assert `sections == ('s','u','m','m','a','r','y')`. Pin current behavior; note as a defect candidate.
  - `should pass a tuple of ReportSchedule instances through when given (ReportSchedule(...),)` — the `all(isinstance(...))` branch.
  - `should return an empty tuple when given []` — assert `== ()` (empty `all()` is `True`, exits via passthrough before `json.loads`).

- [x] **Task 10: report-schedule raw-exception escapes (pin current behavior)**
  Files: `tests/core/test_config.py`
  Test cases:
  - `should raise TypeError, not ValidationError, when given a list of plain dicts` — `pytest.raises(TypeError)` (`all(isinstance)` False → `json.loads(list)`); flag as defect candidate.
  - `should raise KeyError, not ValidationError, when a schedule object omits sections` — `pytest.raises(KeyError)` with the bare `'sections'` key.
  - `should raise TypeError when given a JSON object instead of an array` — `'{"name":"d"}'` → `pytest.raises(TypeError)` (string indices must be integers).

- [x] **Task 11: ReportSchedule dataclass semantics**
  Files: `tests/core/test_config.py`
  Test cases:
  - `should compare equal and hash when two ReportSchedules carry the same values` — assert value-equality and that both are usable as set/dict keys.
  - `should raise FrozenInstanceError when a ReportSchedule field is mutated` — `pytest.raises(dataclasses.FrozenInstanceError)`.

### Phase 5: `postgres_dsn` composition

- [x] **Task 12: DSN composition**
  Files: `tests/core/test_config.py`
  Test cases:
  - `should compose the default DSN byte-for-byte when no postgres fields are overridden` — `monkeypatch.delenv` all five `POSTGRES_*` keys, assert exactly `postgresql://herald_username:herald_password@localhost:5432/herald_database`. (This is the invariant half of task 19.2's percent-encoding guard — survives that fix unchanged.)
  - `should interpolate every component in order when all five postgres fields are overridden` — distinct sentinels (`u1`/`p1`/`h1`/`1234`/`d1`), assert `postgresql://u1:p1@h1:1234/d1` so a transposed component is visible.
  - `should render an int port with no quoting when postgres_port is supplied as the string "6543"` — assert the DSN contains `:6543/` (pydantic coerces str→int; env vars are always strings).

### Phase 6: `get_settings` caching and the env-var (`NoDecode`) path

- [x] **Task 13: lru_cache behavior**
  Files: `tests/core/test_config.py`
  Test cases:
  - `should return the identical object on repeated calls` — assert `get_settings() is get_settings()`.
  - `should keep serving the first-seen values after the environment changes` — set `SERVE_ALLOWLIST=1,2`, call `get_settings()`, then set `SERVE_ALLOWLIST=9` and assert `frozenset({1, 2})` is still returned (cache is intended behavior).
  - `should observe the new environment after cache_clear()` — after `cache_clear()`, the new `SERVE_ALLOWLIST` value is read.

- [x] **Task 14: env-var path exercises NoDecode**
  Files: `tests/core/test_config.py`
  Test cases:
  - `should read SERVE_ALLOWLIST / TELEGRAM_CHANNELS / PROJECT_EDGES through the env-var path` — via `monkeypatch.setenv` + `cache_clear()`, assert each parses end-to-end (e.g. `SERVE_ALLOWLIST=1,2` → `frozenset({1, 2})`). This is the only test exercising `NoDecode`; without it pydantic-settings would JSON-decode the env value before the validators run.
