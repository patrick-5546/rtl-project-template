import argparse
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from flow import cli


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
        pytest.raises(SystemExit, match="no matching build_and_test variant"),
    ):
        cli.run_regression(
            "verilator",
            dut="top",
            sources_file="rtl/sources.vf",
            config="width4",
        )


def test_selected_config_accepts_matching_variant(tmp_path: Path) -> None:
    def run_and_match(
        command: list[str],
        *,
        cwd: Path,
        env: dict[str, str],
        check: bool,
    ) -> subprocess.CompletedProcess[list[str]]:
        del command, cwd, check
        Path(env["COCOTB_CONFIG_MATCH_FILE"]).touch()
        return subprocess.CompletedProcess(args=[], returncode=0)

    with (
        patch.object(cli, "PROJECT_DIR", tmp_path),
        patch.object(cli, "_sim"),
        patch.object(cli.subprocess, "run", side_effect=run_and_match),
    ):
        cli.run_regression(
            "verilator",
            dut="top",
            sources_file="rtl/sources.vf",
            config="width4",
        )
