import argparse
import subprocess
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from flow import cli
from flow.simulators import SimulatorProfile


@pytest.fixture
def project(tmp_path: Path) -> Iterator[Path]:
    """A project with DUT ``top`` in two configurations and an unconfigured ``other``."""
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "cocotb_configs.py").write_text(
        "HDL_CONFIGS = {'top': {'width4': {'WIDTH': 4}, 'width8': {'WIDTH': 8}}}\n",
        encoding="utf-8",
    )
    for harness in ("test_top.py", "test_top__smoke.py", "test_other.py"):
        (tests / harness).touch()
    with patch.object(cli, "PROJECT_DIR", tmp_path), patch.object(cli, "TESTS_DIR", tests):
        yield tmp_path


@pytest.mark.parametrize(
    ("dut", "config", "expected"),
    [
        ("top", None, [("top", "width4"), ("top", "width8")]),
        ("top", "width8", [("top", "width8")]),
        ("all", None, [("other", "default"), ("top", "width4"), ("top", "width8")]),
    ],
)
@pytest.mark.usefixtures("project")
def test_selected_cases(dut: str, config: str | None, expected: list[tuple[str, str]]) -> None:
    assert cli._selected_cases(dut, config) == expected


@pytest.mark.parametrize(
    ("dut", "config", "message"),
    [
        ("all", "width4", "cannot be combined"),
        ("top", "width16", "Unknown CONFIG 'width16'"),
        ("nope", None, "Unknown DUT 'nope'"),
    ],
)
@pytest.mark.usefixtures("project")
def test_selected_cases_reject(dut: str, config: str | None, message: str) -> None:
    with pytest.raises(SystemExit, match=message):
        cli._selected_cases(dut, config)


@pytest.mark.usefixtures("project")
def test_single_case_takes_the_only_config() -> None:
    assert cli._single_case("other", None) == ("other", "default")


@pytest.mark.parametrize(
    ("dut", "message"),
    [("top", "multiple configurations"), ("all", "Set DUT to one module")],
)
@pytest.mark.usefixtures("project")
def test_single_case_requires_one(dut: str, message: str) -> None:
    with pytest.raises(SystemExit, match=message):
        cli._single_case(dut, None)


def test_viewer_rejects_simulator_without_one() -> None:
    with (
        patch.object(cli, "_sim"),
        pytest.raises(SystemExit, match="SIM=icarus has no waveform viewer"),
    ):
        cli._viewer("icarus")


def record_cases(cases: str) -> MagicMock:
    """A fake pytest run whose build_and_test calls ran *cases*."""

    def run_and_record(
        command: list[str],
        *,
        cwd: Path,
        env: dict[str, str],
        check: bool,
    ) -> subprocess.CompletedProcess[list[str]]:
        del command, cwd, check
        Path(env["COCOTB_EXECUTED_CASES_FILE"]).write_text(cases, encoding="utf-8")
        return subprocess.CompletedProcess(args=[], returncode=0)

    return MagicMock(side_effect=run_and_record)


@pytest.mark.parametrize(
    ("dut", "config", "ran", "missing"),
    [
        ("top", "width4", "", r"top\.width4"),
        ("all", None, "top\twidth4\nother\tdefault\n", r"top\.width8"),
    ],
)
@pytest.mark.usefixtures("project")
def test_regression_requires_every_selected_case(
    dut: str, config: str | None, ran: str, missing: str
) -> None:
    with (
        patch.object(cli, "_sim"),
        patch.object(cli.subprocess, "run", record_cases(ran)),
        pytest.raises(SystemExit, match=rf"No build_and_test call ran: {missing}\."),
    ):
        cli.run_regression("verilator", dut=dut, sources_file="rtl/sources.vf", config=config)


@pytest.mark.usefixtures("project")
def test_regression_runs_each_selected_case_by_node_id() -> None:
    run = record_cases("top\twidth4\ntop\twidth8\n")
    with patch.object(cli, "_sim"), patch.object(cli.subprocess, "run", run):
        cli.run_regression("verilator", dut="top", sources_file="rtl/sources.vf", config=None)
    assert run.call_args.args[0][-2:] == [
        "tests/test_top.py::test_top[width4]",
        "tests/test_top.py::test_top[width8]",
    ]


@pytest.mark.usefixtures("project")
def test_regression_explains_a_missing_harness(capsys: pytest.CaptureFixture[str]) -> None:
    not_found = subprocess.CompletedProcess(args=[], returncode=cli.PYTEST_USAGE_ERROR)
    with (
        patch.object(cli, "_sim"),
        patch.object(cli.subprocess, "run", return_value=not_found),
        pytest.raises(SystemExit) as error,
    ):
        cli.run_regression("verilator", dut="other", sources_file="rtl/sources.vf", config=None)
    assert error.value.code == cli.PYTEST_USAGE_ERROR
    assert "test_<dut> in tests/test_<dut>.py" in capsys.readouterr().err


@pytest.mark.usefixtures("project")
def test_report_coverage_attempts_every_case() -> None:
    def coverage_data_path(build_dir: Path) -> Path:
        return build_dir / "coverage.dat"

    profile = MagicMock(spec=SimulatorProfile)
    profile.name = "verilator"
    profile.supports_coverage = True
    profile.coverage_data_path.side_effect = coverage_data_path
    profile.report_coverage.side_effect = [SystemExit(3), None]
    args = argparse.Namespace(sim="verilator", dut="top", config=None)
    with (
        patch.object(cli, "_sim", return_value=profile),
        pytest.raises(SystemExit) as error,
    ):
        cli.cmd_report_coverage(args)
    assert error.value.code == 3
    assert profile.report_coverage.call_count == 2
