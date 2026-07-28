from datetime import timedelta

import pytest

from src.changelog.report import TimeWindow, report_for_schedule, schedule_by_name
from src.core.config import ReportSchedule, Settings


def test_report_schedules_json_string_parses_to_tuple_of_dataclasses():
    settings = Settings(
        github_webhook_secret="x",
        telegram_bot_token="x",
        report_schedules='[{"name":"daily","window":1,"sections":["summary","per_branch","remaining"]}]',
    )

    assert settings.report_schedules == (
        ReportSchedule(name="daily", window=1, sections=("summary", "per_branch", "remaining")),
    )


def test_report_schedules_empty_or_unset_yields_empty_tuple():
    assert Settings(github_webhook_secret="x", telegram_bot_token="x").report_schedules == ()
    assert (
        Settings(github_webhook_secret="x", telegram_bot_token="x", report_schedules="").report_schedules
        == ()
    )


def test_report_for_schedule_builds_time_window_and_ordered_sections(make_fake_section):
    registry = {
        "summary": make_fake_section("s"),
        "per_branch": make_fake_section("p"),
        "remaining": make_fake_section("r"),
    }
    schedule = ReportSchedule(name="daily", window=1, sections=("summary", "per_branch", "remaining"))

    report = report_for_schedule(schedule, registry)

    assert report.window == TimeWindow(timedelta(days=1))
    assert report.sections == [registry["summary"], registry["per_branch"], registry["remaining"]]


def test_report_for_schedule_raises_on_unknown_section_key(make_fake_section):
    registry = {"summary": make_fake_section("s")}
    schedule = ReportSchedule(name="daily", window=1, sections=("summary", "missing_key"))

    with pytest.raises(ValueError, match="missing_key"):
        report_for_schedule(schedule, registry)


def test_schedule_by_name_raises_on_unknown_name():
    schedules = (ReportSchedule(name="daily", window=1, sections=("summary",)),)

    with pytest.raises(ValueError, match="nope"):
        schedule_by_name(schedules, "nope")
