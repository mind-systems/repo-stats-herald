from src.changelog.report import Report


async def test_none_dropped_order_preserved(make_fake_section, counting_window):
    sec_a = make_fake_section("A")
    sec_b = make_fake_section(None)
    sec_c = make_fake_section("C")
    report = Report(counting_window, [sec_a, sec_b, sec_c])

    result = await report.build("repo", 1)

    assert result == "A\n\nC"


async def test_all_none_yields_none(make_fake_section, counting_window):
    sections = [make_fake_section(None), make_fake_section(None)]
    report = Report(counting_window, sections)

    result = await report.build("repo", 1)

    assert result is None


async def test_single_surviving_section_has_no_join_artifacts(make_fake_section, counting_window):
    sections = [make_fake_section(None), make_fake_section("only"), make_fake_section(None)]
    report = Report(counting_window, sections)

    result = await report.build("repo", 1)

    assert result == "only"


async def test_window_resolved_exactly_once_and_shared_across_sections(
    make_fake_section, counting_window
):
    sec_a = make_fake_section("A")
    sec_b = make_fake_section("B")
    report = Report(counting_window, [sec_a, sec_b])

    await report.build("repo", 1)

    assert counting_window.resolve_count == 1
    assert sec_a.calls[0][2:4] == ("before-sha", "after-sha")
    assert sec_b.calls[0][2:4] == ("before-sha", "after-sha")


async def test_lang_threaded_through_to_every_section(make_fake_section, counting_window):
    sec_a = make_fake_section("A")
    sec_b = make_fake_section("B")
    report = Report(counting_window, [sec_a, sec_b])

    await report.build("repo", 1, lang="de")

    assert sec_a.calls[0][4] == "de"
    assert sec_b.calls[0][4] == "de"


async def test_lang_defaults_to_ru(make_fake_section, counting_window):
    sec_a = make_fake_section("A")
    report = Report(counting_window, [sec_a])

    await report.build("repo", 1)

    assert sec_a.calls[0][4] == "ru"


async def test_repo_and_org_id_threaded_to_every_section(make_fake_section, counting_window):
    sec_a = make_fake_section("A")
    sec_b = make_fake_section("B")
    report = Report(counting_window, [sec_a, sec_b])

    await report.build("my-repo", 42)

    assert sec_a.calls[0][:2] == ("my-repo", 42)
    assert sec_b.calls[0][:2] == ("my-repo", 42)
