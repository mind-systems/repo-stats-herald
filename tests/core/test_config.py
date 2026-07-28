"""Tests for `Settings`' hand-written `mode="before"` validators and the
`postgres_dsn` property: the comma-separated allowlist parser, the shared
JSON-dict/key-coercion validator behind the four dict fields, the
`from>to:kind` project-edge grammar, the report-schedule parser, DSN
composition, and `get_settings` caching. Several cases pin *current*
behavior at known defect candidates (lower-case kind surviving the literal
path, a scalar `sections` string split per character, raw `TypeError`/
`KeyError` escaping instead of `ValidationError`) rather than fixing them.
"""

import dataclasses

import pytest
from pydantic import ValidationError

from src.core.config import ReportSchedule, Settings, get_settings

_POSTGRES_ENV_KEYS = (
    "POSTGRES_HOST",
    "POSTGRES_PORT",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_DB",
)


def make_settings(**overrides: object) -> Settings:
    return Settings(github_webhook_secret="x", telegram_bot_token="x", _env_file=None, **overrides)


@pytest.fixture
def clean_get_settings_cache(monkeypatch: pytest.MonkeyPatch):
    """Supplies get_settings' two required fields via env and clears its
    lru_cache before and after the test, so caching assertions here aren't
    polluted by another test's cached instance or by missing required
    fields."""
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "x")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "x")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# --- serve_allowlist: comma-separated org allowlist ---


def test_should_parse_comma_separated_string_into_frozenset_of_ints():
    allowlist = make_settings(serve_allowlist="1,2,3").serve_allowlist
    assert allowlist == frozenset({1, 2, 3})
    assert isinstance(allowlist, frozenset)


def test_should_strip_whitespace_and_skip_empty_tokens():
    assert make_settings(serve_allowlist=" 1 , 2 ,,").serve_allowlist == frozenset({1, 2})


def test_should_return_empty_frozenset_when_given_blank_string():
    assert make_settings(serve_allowlist="").serve_allowlist == frozenset()


def test_should_pass_set_through_and_coerce_members_to_int():
    assert make_settings(serve_allowlist={"1", "2"}).serve_allowlist == frozenset({1, 2})


def test_should_treat_bare_int_as_single_element_allowlist():
    assert make_settings(serve_allowlist=7).serve_allowlist == frozenset({7})


def test_should_reject_whole_value_when_one_token_is_invalid():
    with pytest.raises(ValidationError):
        make_settings(serve_allowlist="1,abc")


def test_should_reject_list_input():
    with pytest.raises(ValidationError):
        make_settings(serve_allowlist=[1, 2])


def test_should_reject_none_rather_than_defaulting_to_empty():
    with pytest.raises(ValidationError):
        make_settings(serve_allowlist=None)


# --- _parse_json_dict: the four dict fields, key coercion and ordering ---


def test_should_coerce_json_string_keys_to_ints_for_github_org_logins():
    logins = make_settings(github_org_logins='{"244165546":"mind-systems"}').github_org_logins
    assert 244165546 in logins
    assert "244165546" not in logins


def test_should_keep_string_keys_as_strings_for_canonical_refs():
    refs = make_settings(canonical_refs='{"repo-name":"main"}').canonical_refs
    assert "repo-name" in refs
    assert isinstance(next(iter(refs)), str)


def test_should_pass_dict_through_and_coerce_keys_for_telegram_channels():
    assert make_settings(telegram_channels={"1": "a"}).telegram_channels == {1: "a"}


def test_should_return_empty_dict_when_given_blank_string():
    assert make_settings(canonical_refs="").canonical_refs == {}


def test_should_return_empty_dict_when_given_none():
    assert make_settings(canonical_refs=None).canonical_refs == {}


def test_should_return_empty_dict_when_given_empty_dict():
    assert make_settings(canonical_refs={}).canonical_refs == {}


def test_should_reject_unparseable_json():
    with pytest.raises(ValidationError):
        make_settings(canonical_refs="notjson")


def test_should_reject_json_array():
    with pytest.raises(ValidationError):
        make_settings(canonical_refs='["a"]')


def test_should_reject_non_string_values_for_canonical_refs():
    with pytest.raises(ValidationError):
        make_settings(canonical_refs='{"a":1}')


# --- _parse_project_edges: the from>to:kind grammar ---


def test_should_parse_single_from_to_kind_token():
    edges = make_settings(project_edges="mind_api>mind_mobile:CONTRACT").project_edges
    assert edges == (("mind_api", "mind_mobile", "CONTRACT"),)


def test_should_uppercase_kind_and_strip_whitespace_around_every_part():
    assert make_settings(project_edges=" a > b : contract ").project_edges == (("a", "b", "CONTRACT"),)


def test_should_parse_multiple_edges_and_skip_empty_tokens():
    edges = make_settings(project_edges="a>b:CONTRACT, ,c>d:AUTH").project_edges
    assert edges == (("a", "b", "CONTRACT"), ("c", "d", "AUTH"))


def test_should_return_empty_tuple_when_given_blank_or_none_or_empty_tuple():
    assert make_settings(project_edges="").project_edges == ()
    assert make_settings(project_edges=None).project_edges == ()
    assert make_settings(project_edges=()).project_edges == ()


def test_should_not_normalize_kind_when_given_prebuilt_list_of_triples():
    # Pins the silent divergence between the literal-list path (no
    # normalization) and the string path (upper-cased) — a defect
    # candidate, not fixed here.
    edges = make_settings(project_edges=[("a", "b", "contract")]).project_edges
    assert edges == (("a", "b", "contract"),)


def test_should_accept_unknown_kind_without_complaint():
    assert make_settings(project_edges="a>b:bogus").project_edges == (("a", "b", "BOGUS"),)


def test_should_fold_extra_gt_into_repo_name():
    assert make_settings(project_edges="a>b>c:AUTH").project_edges == (("a", "b>c", "AUTH"),)


def test_should_reject_token_missing_gt():
    with pytest.raises(ValidationError, match="malformed PROJECT_EDGES token"):
        make_settings(project_edges="ab:CONTRACT")


def test_should_reject_token_missing_colon():
    with pytest.raises(ValidationError):
        make_settings(project_edges="a>b")


def test_should_produce_unpack_error_when_separators_are_inverted():
    # The guard only checks presence of '>' and ':', not their order, so an
    # inverted token like "a:b>c" passes the guard and fails unpacking
    # instead. Pinned as a known gap, not fixed here.
    with pytest.raises(ValidationError):
        make_settings(project_edges="a:b>c")


# --- _parse_report_schedules: JSON array of ReportSchedule ---


def test_should_parse_two_schedule_env_example_value():
    value = (
        '[{"name":"daily","window":1,"sections":["summary","per_branch","remaining"]},'
        '{"name":"weekly","window":7,"sections":["summary"]}]'
    )
    schedules = make_settings(report_schedules=value).report_schedules
    assert schedules == (
        ReportSchedule(name="daily", window=1, sections=("summary", "per_branch", "remaining")),
        ReportSchedule(name="weekly", window=7, sections=("summary",)),
    )


def test_should_coerce_string_window_to_int():
    schedules = make_settings(report_schedules='[{"name":"d","window":"7","sections":["s"]}]').report_schedules
    assert schedules[0].window == 7
    assert isinstance(schedules[0].window, int)


def test_should_split_string_sections_into_per_character_entries():
    # Pins current behavior: a scalar `sections` string is iterated
    # character-by-character rather than treated as one section name — a
    # defect candidate, not fixed here.
    schedules = make_settings(report_schedules='[{"name":"d","window":1,"sections":"summary"}]').report_schedules
    assert schedules[0].sections == ("s", "u", "m", "m", "a", "r", "y")


def test_should_pass_through_tuple_of_report_schedule_instances():
    schedule = ReportSchedule(name="d", window=1, sections=("s",))
    assert make_settings(report_schedules=(schedule,)).report_schedules == (schedule,)


def test_should_return_empty_tuple_when_given_empty_list():
    assert make_settings(report_schedules=[]).report_schedules == ()


def test_should_raise_type_error_when_given_list_of_plain_dicts():
    # Pins current behavior: a list that isn't all-ReportSchedule falls
    # through to json.loads(list), which raises a raw TypeError instead of
    # a ValidationError — a defect candidate, not fixed here.
    with pytest.raises(TypeError):
        make_settings(report_schedules=[{"name": "d", "window": 1, "sections": ["s"]}])


def test_should_raise_key_error_when_schedule_omits_sections():
    with pytest.raises(KeyError):
        make_settings(report_schedules='[{"name":"d","window":1}]')


def test_should_raise_type_error_when_given_json_object_instead_of_array():
    with pytest.raises(TypeError):
        make_settings(report_schedules='{"name":"d"}')


def test_should_compare_equal_and_hash_for_same_values():
    a = ReportSchedule(name="d", window=1, sections=("s",))
    b = ReportSchedule(name="d", window=1, sections=("s",))
    assert a == b
    assert hash(a) == hash(b)
    assert {a, b} == {a}
    assert {a: "x"}[b] == "x"


def test_should_raise_frozen_instance_error_when_mutated():
    schedule = ReportSchedule(name="d", window=1, sections=("s",))
    with pytest.raises(dataclasses.FrozenInstanceError):
        schedule.name = "changed"


# --- postgres_dsn composition ---


def test_should_compose_default_dsn_byte_for_byte(monkeypatch: pytest.MonkeyPatch):
    for key in _POSTGRES_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    settings = make_settings()
    assert settings.postgres_dsn == "postgresql://herald_username:herald_password@localhost:5432/herald_database"


def test_should_interpolate_every_overridden_component_in_order():
    settings = make_settings(
        postgres_user="u1",
        postgres_password="p1",
        postgres_host="h1",
        postgres_port=1234,
        postgres_db="d1",
    )
    assert settings.postgres_dsn == "postgresql://u1:p1@h1:1234/d1"


def test_should_render_int_port_with_no_quoting_when_given_string_port():
    settings = make_settings(postgres_port="6543")
    assert ":6543/" in settings.postgres_dsn


# --- get_settings caching and the env-var (NoDecode) path ---


def test_should_return_identical_object_on_repeated_calls(clean_get_settings_cache: None):
    assert get_settings() is get_settings()


def test_should_keep_serving_first_seen_values_after_env_changes(
    monkeypatch: pytest.MonkeyPatch, clean_get_settings_cache: None
):
    monkeypatch.setenv("SERVE_ALLOWLIST", "1,2")
    first = get_settings()
    assert first.serve_allowlist == frozenset({1, 2})
    monkeypatch.setenv("SERVE_ALLOWLIST", "9")
    assert get_settings().serve_allowlist == frozenset({1, 2})


def test_should_observe_new_env_after_cache_clear(monkeypatch: pytest.MonkeyPatch, clean_get_settings_cache: None):
    monkeypatch.setenv("SERVE_ALLOWLIST", "1,2")
    get_settings()
    monkeypatch.setenv("SERVE_ALLOWLIST", "9")
    get_settings.cache_clear()
    assert get_settings().serve_allowlist == frozenset({9})


def test_should_read_dict_and_allowlist_and_edge_fields_through_env_var_path(
    monkeypatch: pytest.MonkeyPatch, clean_get_settings_cache: None
):
    monkeypatch.setenv("SERVE_ALLOWLIST", "1,2")
    monkeypatch.setenv("TELEGRAM_CHANNELS", '{"1":"a"}')
    monkeypatch.setenv("PROJECT_EDGES", "a>b:CONTRACT")
    settings = get_settings()
    assert settings.serve_allowlist == frozenset({1, 2})
    assert settings.telegram_channels == {1: "a"}
    assert settings.project_edges == (("a", "b", "CONTRACT"),)
