"""Tests pinning the `PivotLocalizer`/`NativeLocalizer` dispatch contract
against mocked collaborators — call counts, arguments, and the exact result
key set — ahead of the real implementation.

These are RED against the raising stubs in `src/reasoning/localizer.py`:
every `notes` call here raises `NotImplementedError` until the strategies are
implemented. Translation/narration text quality is the eval harness's
concern, not asserted here.
"""

from src.reasoning.localizer import NativeLocalizer, PivotLocalizer


async def test_pivot_localizer_narrates_pivot_once_and_translates_the_rest_when_pivot_requested(
    make_change, fake_narrating_reasoner, fake_translator
):
    change = make_change()
    localizer = PivotLocalizer(fake_narrating_reasoner, fake_translator, pivot="en")

    result = await localizer.notes(change, {"ru", "en"})

    assert fake_narrating_reasoner.calls == [(change, "en")]
    assert fake_translator.calls == [("narrated:en", "ru", "en")]
    assert result["en"] == "narrated:en"
    assert result["ru"] == "translated:ru:en"
    assert set(result.keys()) == {"ru", "en"}


async def test_pivot_localizer_still_narrates_pivot_once_when_pivot_not_requested(
    make_change, fake_narrating_reasoner, fake_translator
):
    change = make_change()
    localizer = PivotLocalizer(fake_narrating_reasoner, fake_translator, pivot="en")

    result = await localizer.notes(change, {"ru", "de"})

    assert fake_narrating_reasoner.calls == [(change, "en")]
    assert sorted(fake_translator.calls) == sorted(
        [("narrated:en", "ru", "en"), ("narrated:en", "de", "en")]
    )
    assert set(result.keys()) == {"ru", "de"}
    assert "en" not in result


async def test_pivot_localizer_uses_configured_pivot_as_source_lang_not_the_default(
    make_change, fake_narrating_reasoner, fake_translator
):
    # A non-"en" pivot so `source_lang=pivot` is genuinely exercised rather
    # than passing by coincidence with `translate`'s "en" default.
    change = make_change()
    localizer = PivotLocalizer(fake_narrating_reasoner, fake_translator, pivot="ru")

    result = await localizer.notes(change, {"en"})

    assert fake_narrating_reasoner.calls == [(change, "ru")]
    assert fake_translator.calls == [("narrated:ru", "en", "ru")]
    assert result == {"en": "translated:en:ru"}


async def test_native_localizer_narrates_once_per_requested_language(
    make_change, fake_narrating_reasoner, fake_translator
):
    change = make_change()
    localizer = NativeLocalizer(fake_narrating_reasoner)

    result = await localizer.notes(change, {"ru", "en"})

    assert len(fake_narrating_reasoner.calls) == 2
    assert {lang for _, lang in fake_narrating_reasoner.calls} == {"ru", "en"}
    assert all(recorded_change == change for recorded_change, _ in fake_narrating_reasoner.calls)
    assert result == {"ru": "narrated:ru", "en": "narrated:en"}
    assert fake_translator.calls == []


async def test_pivot_localizer_empty_langs_yields_empty_dict_and_no_calls(
    make_change, fake_narrating_reasoner, fake_translator
):
    change = make_change()
    localizer = PivotLocalizer(fake_narrating_reasoner, fake_translator, pivot="en")

    result = await localizer.notes(change, set())

    assert result == {}
    assert fake_narrating_reasoner.calls == []
    assert fake_translator.calls == []


async def test_native_localizer_empty_langs_yields_empty_dict_and_no_calls(
    make_change, fake_narrating_reasoner
):
    change = make_change()
    localizer = NativeLocalizer(fake_narrating_reasoner)

    result = await localizer.notes(change, set())

    assert result == {}
    assert fake_narrating_reasoner.calls == []


async def test_pivot_localizer_result_keys_match_requested_langs_exactly(
    make_change, fake_narrating_reasoner, fake_translator
):
    change = make_change()
    localizer = PivotLocalizer(fake_narrating_reasoner, fake_translator, pivot="en")

    result = await localizer.notes(change, {"ru", "de", "en"})

    assert set(result.keys()) == {"ru", "de", "en"}


async def test_native_localizer_result_keys_match_requested_langs_exactly(
    make_change, fake_narrating_reasoner
):
    change = make_change()
    localizer = NativeLocalizer(fake_narrating_reasoner)

    result = await localizer.notes(change, {"ru", "de", "en"})

    assert set(result.keys()) == {"ru", "de", "en"}


async def test_pivot_localizer_report_notes_builds_pivot_once_and_translates_the_rest(
    fake_narrating_reasoner, fake_translator, fake_report
):
    localizer = PivotLocalizer(fake_narrating_reasoner, fake_translator, pivot="en")

    result = await localizer.report_notes(fake_report, "api", 1, {"ru", "en"})

    assert fake_report.calls == [("api", 1, "en")]
    assert fake_translator.calls == [("report:en", "ru", "en")]
    assert result["en"] == "report:en"
    assert result["ru"] == "translated:ru:en"
    assert set(result.keys()) == {"ru", "en"}


async def test_pivot_localizer_report_notes_uses_configured_pivot_as_source_lang_not_the_default(
    fake_narrating_reasoner, fake_translator, fake_report
):
    # A non-"en" pivot so `source_lang=pivot` is genuinely exercised rather
    # than passing by coincidence with `translate`'s "en" default.
    localizer = PivotLocalizer(fake_narrating_reasoner, fake_translator, pivot="ru")

    result = await localizer.report_notes(fake_report, "api", 1, {"en"})

    assert fake_report.calls == [("api", 1, "ru")]
    assert fake_translator.calls == [("report:ru", "en", "ru")]
    assert result == {"en": "translated:en:ru"}


async def test_native_localizer_report_notes_builds_once_per_requested_language(
    fake_narrating_reasoner, fake_translator, fake_report
):
    localizer = NativeLocalizer(fake_narrating_reasoner)

    result = await localizer.report_notes(fake_report, "api", 1, {"ru", "en"})

    assert len(fake_report.calls) == 2
    assert {(repo, org_id) for repo, org_id, _ in fake_report.calls} == {("api", 1)}
    assert {lang for _, _, lang in fake_report.calls} == {"ru", "en"}
    assert result == {"ru": "report:ru", "en": "report:en"}
    assert fake_translator.calls == []


async def test_pivot_localizer_report_notes_empty_langs_yields_empty_dict_and_no_calls(
    fake_narrating_reasoner, fake_translator, fake_report
):
    localizer = PivotLocalizer(fake_narrating_reasoner, fake_translator, pivot="en")

    result = await localizer.report_notes(fake_report, "api", 1, set())

    assert result == {}
    assert fake_report.calls == []
    assert fake_translator.calls == []


async def test_native_localizer_report_notes_empty_langs_yields_empty_dict_and_no_calls(
    fake_narrating_reasoner, fake_report
):
    localizer = NativeLocalizer(fake_narrating_reasoner)

    result = await localizer.report_notes(fake_report, "api", 1, set())

    assert result == {}
    assert fake_report.calls == []


async def test_pivot_localizer_report_notes_none_report_maps_every_lang_to_none_without_translating(
    fake_narrating_reasoner, fake_translator, fake_report
):
    fake_report.result = None
    localizer = PivotLocalizer(fake_narrating_reasoner, fake_translator, pivot="en")

    result = await localizer.report_notes(fake_report, "api", 1, {"ru", "en"})

    assert result == {"ru": None, "en": None}
    assert fake_report.calls == [("api", 1, "en")]
    assert fake_translator.calls == []


async def test_native_localizer_report_notes_none_report_maps_every_lang_to_none(
    fake_narrating_reasoner, fake_translator, fake_report
):
    fake_report.result = None
    localizer = NativeLocalizer(fake_narrating_reasoner)

    result = await localizer.report_notes(fake_report, "api", 1, {"ru", "en"})

    assert result == {"ru": None, "en": None}
    assert fake_translator.calls == []
