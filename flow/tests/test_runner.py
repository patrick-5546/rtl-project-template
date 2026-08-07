import logging
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from flow.runner import (
    SimArgs,
    active_parameter,
    artifact_build_mode,
    build_and_test,
    build_jobs,
    default_build_dir,
    default_coverage_dat,
    discover_configs,
    discover_duts,
    expose_tool_on_path,
    make_target_command,
    validate_config_name,
)
from flow.simulators import SIMULATORS, SimulatorProfile


@pytest.mark.parametrize(
    ("waves", "coverage", "expected"),
    [
        (False, False, "normal"),
        (True, False, "waves"),
        (False, True, "coverage"),
        (True, True, "waves-coverage"),
    ],
)
def test_artifact_build_mode(waves: bool, coverage: bool, expected: str) -> None:
    assert artifact_build_mode(waves=waves, hdl_coverage=coverage) == expected


def test_default_build_dir_isolates_config_and_artifact(tmp_path: Path) -> None:
    assert default_build_dir(tmp_path, "top", "verilator", "width4", "waves") == (
        tmp_path / "build" / "top" / "verilator" / "width4" / "waves"
    )


def test_default_build_dir_appends_to_override(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BUILD_DIR", "custom")
    assert default_build_dir(tmp_path, "top", "verilator", "width8", "coverage") == (
        tmp_path / "custom" / "width8" / "coverage"
    )


def test_coverage_path_is_canonical(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("COVERAGE_DAT", "wrong.dat")
    build_dir = tmp_path / "build"
    assert default_coverage_dat(build_dir, SIMULATORS["questa"]) == (build_dir / "coverage.ucdb")


@pytest.mark.parametrize("name", ["width4", "default", "fast.debug-1"])
def test_validate_config_name_accepts_safe_names(name: str) -> None:
    assert validate_config_name(name) == name


@pytest.mark.parametrize("name", ["", "../bad", "/absolute", "bad name"])
def test_validate_config_name_rejects_unsafe_names(name: str) -> None:
    with pytest.raises(ValueError, match="config must start"):
        validate_config_name(name)


def test_discover_configs_loads_manifest(tmp_path: Path) -> None:
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "cocotb_configs.py").write_text(
        "HDL_CONFIGS = {'top': {'width4': {'WIDTH': 4}, 'width8': {'WIDTH': 8}}}\n"
    )
    assert discover_configs(tmp_path, "top") == {
        "width4": {"WIDTH": 4},
        "width8": {"WIDTH": 8},
    }


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("HDL_CONFIGS = []\n", "HDL_CONFIGS must be a mapping"),
        ("HDL_CONFIGS = {'top': []}\n", r"HDL_CONFIGS\['top'\] must be a mapping"),
        ("HDL_CONFIGS = {'top': {1: {}}}\n", "configuration names must be strings"),
        ("HDL_CONFIGS = {'top': {'width4': 4}}\n", "parameters for top/width4"),
    ],
)
def test_discover_configs_rejects_invalid_manifest(
    tmp_path: Path,
    body: str,
    message: str,
) -> None:
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "cocotb_configs.py").write_text(body)
    with pytest.raises((TypeError, ValueError), match=message):
        discover_configs(tmp_path, "top")


def test_discover_duts_deduplicates_filename_variants(tmp_path: Path) -> None:
    for name in ("test_top.py", "test_top__smoke.py", "test_other.py"):
        (tmp_path / name).touch()
    assert discover_duts(tmp_path) == ["other", "top"]


def test_active_parameter_uses_exported_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COCOTB_PARAM_WIDTH", "12")
    assert active_parameter("WIDTH", 8) == 12


def test_build_jobs_is_explicit_and_capped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BUILD_JOBS", "999")
    monkeypatch.setattr("flow.runner.os.cpu_count", lambda: 6)
    assert build_jobs() == 6


def test_executable_override_is_exposed_on_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable = tmp_path / "tools" / "verilator"
    monkeypatch.setenv("VERILATOR", str(executable))
    monkeypatch.setenv("PATH", f"/usr/bin{os.pathsep}{executable.parent}")
    expose_tool_on_path("VERILATOR")
    assert Path(os.environ["PATH"].split(os.pathsep)[0]) == executable.parent


def test_make_target_command_retains_selectors() -> None:
    assert (
        make_target_command(
            "waves",
            simulator="verilator",
            dut="top",
            config="width4",
            viewer="surfer",
            hdl_coverage=True,
        )
        == "make waves SIM=verilator DUT=top VIEWER=surfer CONFIG=width4 HDL_COVERAGE=1"
    )


def test_wave_metadata_is_prepared_before_a_failing_test(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    profile = MagicMock(spec=SimulatorProfile)
    profile.no_covergroups = True
    profile.supports_coverage = True
    profile.supports_gui = False
    profile.forces_ansi_on_tty = False
    profile.configure.return_value = SimArgs()
    profile.coverage_data_path.return_value = tmp_path / "coverage.dat"
    profile.wave_path.return_value = tmp_path / "dump.fst"

    def prepare(*args: object) -> None:
        del args
        events.append("prepare")

    profile.prepare_waves.side_effect = prepare
    simulator = MagicMock()
    simulator.log = logging.getLogger("flow-test-wave-order")
    simulator.build.side_effect = lambda **kwargs: events.append("build")

    def fail_test(**kwargs: object) -> None:
        del kwargs
        events.append("test")
        raise RuntimeError("simulated test failure")

    simulator.test.side_effect = fail_test
    monkeypatch.setitem(SIMULATORS, "verilator", profile)
    monkeypatch.setenv("SIM", "verilator")
    monkeypatch.setenv("DUT", "top")
    monkeypatch.setenv("SV_SOURCES_FILE", "rtl/sources.vf")
    monkeypatch.setenv("BUILD_DIR", str(tmp_path / "build"))
    monkeypatch.setenv("WAVES", "1")
    monkeypatch.delenv("CONFIG", raising=False)
    monkeypatch.delenv("HDL_COVERAGE", raising=False)

    with (
        patch("flow.runner.get_runner", return_value=simulator),
        pytest.raises(RuntimeError, match="simulated test failure"),
    ):
        build_and_test("test_top")

    assert events == ["build", "prepare", "test"]
