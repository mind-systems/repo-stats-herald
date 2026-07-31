"""`EvalRunner.run`: writes each case's output, then reports which cases have
no matching reference note under a separate reference directory."""

from pathlib import Path

from scripts.eval import Case, CaseHandler, EvalRunner


class _StubCaseHandler(CaseHandler):
    """Returns a fixed string with no live model, pool, or SSH tunnel."""

    async def run(self, inputs: dict) -> str:
        return "stub output"


def _make_runner(out_dir: Path, reference_dir: Path) -> EvalRunner:
    return EvalRunner({"stub": _StubCaseHandler()}, out_dir=out_dir, reference_dir=reference_dir)


def _cases(*names: str) -> list[Case]:
    return [Case(name=name, type="stub", inputs={}) for name in names]


async def test_run_reports_every_case_when_no_reference_exists(tmp_path, capsys):
    out_dir = tmp_path / "out"
    reference_dir = tmp_path / "reference"
    reference_dir.mkdir()
    runner = _make_runner(out_dir, reference_dir)
    cases = _cases("alpha", "beta")

    result = await runner.run(cases)

    assert result is None
    output = capsys.readouterr().out
    assert "2 of 2 eval cases have no reference to compare against" in output
    assert "alpha" in output
    assert "beta" in output


async def test_run_reports_only_cases_missing_a_reference(tmp_path, capsys):
    out_dir = tmp_path / "out"
    reference_dir = tmp_path / "reference"
    reference_dir.mkdir()
    (reference_dir / "alpha.md").write_text("reference note", encoding="utf-8")
    runner = _make_runner(out_dir, reference_dir)
    cases = _cases("alpha", "beta")

    result = await runner.run(cases)

    assert result is None
    lines = capsys.readouterr().out.strip().splitlines()
    summary_line = lines[-1]
    assert summary_line == "1 of 2 eval cases have no reference to compare against: beta"


async def test_run_reports_no_missing_case_when_every_case_has_a_reference(tmp_path, capsys):
    out_dir = tmp_path / "out"
    reference_dir = tmp_path / "reference"
    reference_dir.mkdir()
    (reference_dir / "alpha.md").write_text("reference note", encoding="utf-8")
    (reference_dir / "beta.md").write_text("reference note", encoding="utf-8")
    runner = _make_runner(out_dir, reference_dir)
    cases = _cases("alpha", "beta")

    result = await runner.run(cases)

    assert result is None
    output = capsys.readouterr().out
    assert "all 2 eval cases have a reference" in output
    assert "no reference to compare against" not in output
