import argparse
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from flow import cli
from flow.simulators import SimulatorProfile


@pytest.mark.parametrize(
    ("requested", "require_multiple", "expected"),
    [
        ("width4", False, "width4"),
        (None, False, None),
    ],
)
def test_resolve_config(
    requested: str | None,
    require_multiple: bool,
    expected: str | None,
) -> None:
    with patch.object(cli, "_configs", return_value={"width4": {}, "width8": {}}):
        assert (
            cli._resolve_config("top", requested, require_for_multiple=require_multiple) == expected
        )


def test_resolve_config_requires_artifact_choice() -> None:
    with (
        patch.object(cli, "_configs", return_value={"width4": {}, "width8": {}}),
        pytest.raises(SystemExit, match="multiple configurations"),
    ):
        cli._resolve_config("top", None, require_for_multiple=True)


def test_wave_selection_uses_simulator_default() -> None:
    simulator, viewer = cli._resolve_wave_selection("vcs", None)
    assert simulator == "vcs"
    assert viewer.name == "verdi"


def test_wave_selection_rejects_incompatible_viewer() -> None:
    with pytest.raises(SystemExit, match="requires SIM=verilator"):
        cli._resolve_wave_selection("vcs", "gtkwave")


def test_test_all_rejects_config() -> None:
    args = argparse.Namespace(
        sim="verilator",
        dut="all",
        sources_file="rtl/sources.vf",
        config="width4",
    )
    with (
        patch.object(cli, "_require_dut"),
        pytest.raises(SystemExit, match="cannot be combined"),
    ):
        cli.cmd_test(args)


def test_selected_config_requires_matching_variant(tmp_path: Path) -> None:
    completed = subprocess.CompletedProcess(args=[], returncode=0)
    with (
        patch.object(cli, "PROJECT_DIR", tmp_path),
        patch.object(cli, "_sim"),
        patch.object(cli.subprocess, "run", return_value=completed),
        pytest.raises(SystemExit, match="No matching build_and_test variant"),
    ):
        cli.run_regression(
            "verilator",
            dut="top",
            sources_file="rtl/sources.vf",
            config="width4",
        )


def test_regression_accepts_complete_config_matrix(tmp_path: Path) -> None:
    def run_and_record(
        command: list[str],
        *,
        cwd: Path,
        env: dict[str, str],
        check: bool,
    ) -> subprocess.CompletedProcess[list[str]]:
        del command, cwd, check
        Path(env["COCOTB_EXECUTED_CASES_FILE"]).write_text("top\twidth4\ntop\twidth8\n")
        return subprocess.CompletedProcess(args=[], returncode=0)

    with (
        patch.object(cli, "PROJECT_DIR", tmp_path),
        patch.object(cli, "_sim"),
        patch.object(cli, "_expected_cases", return_value={("top", "width4"), ("top", "width8")}),
        patch.object(cli.subprocess, "run", side_effect=run_and_record),
    ):
        cli.run_regression(
            "verilator",
            dut="top",
            sources_file="rtl/sources.vf",
            config=None,
        )


def test_regression_rejects_incomplete_all_dut_matrix(tmp_path: Path) -> None:
    def run_and_record(
        command: list[str],
        *,
        cwd: Path,
        env: dict[str, str],
        check: bool,
    ) -> subprocess.CompletedProcess[list[str]]:
        del command, cwd, check
        Path(env["COCOTB_EXECUTED_CASES_FILE"]).write_text("top\twidth4\nother\t\n")
        return subprocess.CompletedProcess(args=[], returncode=0)

    expected = {("top", "width4"), ("top", "width8"), ("other", None)}
    with (
        patch.object(cli, "PROJECT_DIR", tmp_path),
        patch.object(cli, "_sim"),
        patch.object(cli, "_expected_cases", return_value=expected),
        patch.object(cli.subprocess, "run", side_effect=run_and_record),
        pytest.raises(SystemExit, match=r"top\.width8"),
    ):
        cli.run_regression(
            "verilator",
            dut="all",
            sources_file="rtl/sources.vf",
            config=None,
        )


def test_expected_cases_includes_unconfigured_dut() -> None:
    def configs(dut: str) -> dict[str, dict[str, object]]:
        return {"small": {}, "large": {}} if dut == "configured" else {}

    with (
        patch.object(cli, "discover_duts", return_value=["configured", "plain"]),
        patch.object(cli, "_configs", side_effect=configs),
    ):
        assert cli._expected_cases("all") == {
            ("configured", "small"),
            ("configured", "large"),
            ("plain", None),
        }


def test_report_coverage_all_attempts_every_case(tmp_path: Path) -> None:
    def coverage_data_path(build_dir: Path) -> Path:
        return build_dir / "coverage.dat"

    profile = MagicMock(spec=SimulatorProfile)
    profile.name = "verilator"
    profile.supports_coverage = True
    profile.coverage_data_path.side_effect = coverage_data_path
    profile.report_coverage.side_effect = [SystemExit(3), None]
    args = argparse.Namespace(sim="verilator")
    with (
        patch.object(cli, "PROJECT_DIR", tmp_path),
        patch.object(cli, "_sim", return_value=profile),
        patch.object(cli, "_expected_cases", return_value={("top", "width4"), ("top", "width8")}),
        pytest.raises(SystemExit) as error,
    ):
        cli.cmd_report_coverage_all(args)
    assert error.value.code == 3
    assert profile.report_coverage.call_count == 2
