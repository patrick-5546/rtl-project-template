import logging
import os
import platform
import shutil
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from flow.runner import (
    PROJECT_DIR,
    SimArgs,
    active_parameter,
    artifact_build_mode,
    build_and_test,
    build_jobs,
    config_params,
    default_build_dir,
    default_coverage_dat,
    discover_configs,
    discover_duts,
    expose_tool_on_path,
    html_viewer,
    make_target_command,
    run,
    validate_config_name,
    waveform_layout,
)
from flow.simulators import SIMULATORS, SimulatorProfile

# Settings that build_and_test and default_build_dir read, and that would change what
# these tests check if a caller set them, as `make test-flow-py BUILD_DIR=...` does.
RUN_SETTINGS = (
    "ABV",
    "BUILD_DIR",
    "COCOTB_EXECUTED_CASES_FILE",
    "HDL_COVERAGE",
    "QUESTA_GUI",
    "REBUILD",
    "VERILATOR",
    "WAVES",
)


@pytest.fixture(autouse=True)
def default_run_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in RUN_SETTINGS:
        monkeypatch.delenv(name, raising=False)


def test_run_adds_its_environment_and_echoes_it(capsys: pytest.CaptureFixture[str]) -> None:
    check = "import os, sys; sys.exit(os.environ.get('FLOW_TEST') != '1')"
    run([sys.executable, "-c", check], env={"FLOW_TEST": "1"})
    assert capsys.readouterr().out.startswith("+ FLOW_TEST=1 ")


def test_a_configuration_without_its_own_layout_gets_the_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("GTKWAVE_SAVE", raising=False)
    default = tmp_path / "waves" / "top" / "default.gtkw"
    own = tmp_path / "waves" / "top" / "width4.gtkw"
    assert waveform_layout("GTKWAVE_SAVE", tmp_path, "top", "width4", ".gtkw") == default
    own.parent.mkdir(parents=True)
    own.touch()
    assert waveform_layout("GTKWAVE_SAVE", tmp_path, "top", "width4", ".gtkw") == own
    assert waveform_layout("GTKWAVE_SAVE", tmp_path, "top", "width8", ".gtkw") == default
    monkeypatch.setenv("GTKWAVE_SAVE", "mine.gtkw")
    assert waveform_layout("GTKWAVE_SAVE", tmp_path, "top", "width4", ".gtkw") == (
        tmp_path / "mine.gtkw"
    )


@pytest.mark.parametrize(
    ("system", "release", "wslview", "viewer"),
    [
        ("darwin", "25.1.0", None, "open"),
        ("linux", "6.8.0-48-generic", "/usr/bin/wslview", "xdg-open"),
        ("linux", "5.15.167.4-microsoft-standard-WSL2", "/usr/bin/wslview", "wslview"),
        ("linux", "5.15.167.4-microsoft-standard-WSL2", None, "xdg-open"),
    ],
)
def test_html_reports_open_with_the_platforms_opener(
    monkeypatch: pytest.MonkeyPatch,
    system: str,
    release: str,
    wslview: str | None,
    viewer: str,
) -> None:
    def which(name: str) -> str | None:
        return wslview if name == "wslview" else None

    monkeypatch.delenv("HTML_VIEWER", raising=False)
    monkeypatch.setattr(sys, "platform", system)
    monkeypatch.setattr(platform, "release", lambda: release)
    monkeypatch.setattr(shutil, "which", which)
    assert html_viewer() == viewer
    monkeypatch.setenv("HTML_VIEWER", "firefox")
    assert html_viewer() == "firefox"


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


def test_build_dir_override_relocates_only_the_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BUILD_DIR", "custom")
    assert default_build_dir(tmp_path, "top", "verilator", "width8", "coverage") == (
        tmp_path / "custom" / "top" / "verilator" / "width8" / "coverage"
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


def test_config_params_give_each_dut_a_config(tmp_path: Path) -> None:
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "cocotb_configs.py").write_text(
        "HDL_CONFIGS = {'top': {'width4': {'WIDTH': 4}}}\n", encoding="utf-8"
    )
    configured = config_params("test_top__smoke", tmp_path)
    assert [(param.id, *param.values) for param in configured] == [
        ("width4", "width4", {"WIDTH": 4})
    ]
    unconfigured = config_params("test_other", tmp_path)
    assert [(param.id, *param.values) for param in unconfigured] == [("default", "default", {})]


def test_discover_duts_deduplicates_filename_variants(tmp_path: Path) -> None:
    for name in ("test_top.py", "test_top__smoke.py", "test_other.py"):
        (tmp_path / name).touch()
    assert discover_duts(tmp_path) == ["other", "top"]


def test_active_parameter_uses_exported_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COCOTB_PARAM_WIDTH", "12")
    assert active_parameter("WIDTH", 8) == 12


def test_build_jobs_defaults_to_and_is_capped_at_the_cpus(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("flow.runner.os.process_cpu_count", lambda: 6)
    monkeypatch.delenv("BUILD_JOBS", raising=False)
    assert build_jobs() == 6
    monkeypatch.setenv("BUILD_JOBS", "2")
    assert build_jobs() == 2
    monkeypatch.setenv("BUILD_JOBS", "999")
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
            hdl_coverage=True,
        )
        == "make waves SIM=verilator DUT=top CONFIG=width4 HDL_COVERAGE=1"
    )


def test_wave_metadata_is_prepared_before_a_failing_test(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    profile = MagicMock(spec=SimulatorProfile)
    profile.supports_coverage = True
    profile.supports_gui = False
    profile.forces_ansi_on_tty = False
    profile.configure.return_value = SimArgs()
    profile.coverage_data_path.return_value = tmp_path / "coverage.dat"
    profile.wave_path.return_value = tmp_path / "dump.fst"

    def prepare(*args: object, **kwargs: object) -> None:
        del args, kwargs
        events.append("prepare")

    profile.prepare_waves.side_effect = prepare
    simulator = MagicMock()
    simulator.log = logging.getLogger("flow-test-wave-order")

    def record_build(**kwargs: object) -> None:
        del kwargs
        events.append("build")

    simulator.build.side_effect = record_build

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

    with (
        patch("flow.runner.get_runner", return_value=simulator),
        pytest.raises(RuntimeError, match="simulated test failure"),
    ):
        build_and_test("test_top")

    assert events == ["build", "prepare", "test"]


def rebuilds(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, **environment: str) -> bool:
    """Run build_and_test with REBUILD=0 and a fake cocotb runner; return its ``always``."""
    simulator = MagicMock()
    simulator.log = logging.getLogger("flow-test-rebuild")
    monkeypatch.setenv("SIM", "verilator")
    monkeypatch.setenv("BUILD_DIR", str(tmp_path / "build"))
    monkeypatch.setenv("REBUILD", "0")
    for name, value in environment.items():
        monkeypatch.setenv(name, value)
    with (
        patch("flow.runner.get_runner", return_value=simulator),
        patch("flow.simulators.require_tool_version"),
    ):
        build_and_test("test_top", config="width4", parameters={"WIDTH": 4})
    return simulator.build.call_args.kwargs["always"]


def test_rebuild_0_rebuilds_only_when_the_build_inputs_change(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert rebuilds(monkeypatch, tmp_path) is True
    assert rebuilds(monkeypatch, tmp_path) is False
    capsys.readouterr()
    assert rebuilds(monkeypatch, tmp_path, ABV="1") is True
    assert "because its defines changed" in capsys.readouterr().out
    assert rebuilds(monkeypatch, tmp_path, ABV="1") is False


def test_rebuild_0_rebuilds_when_the_record_is_not_an_object(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert rebuilds(monkeypatch, tmp_path) is True
    record = tmp_path / "build" / "top" / "verilator" / "width4" / "normal" / "flow-build.json"
    record.write_text("[]\n", encoding="utf-8")
    capsys.readouterr()
    assert rebuilds(monkeypatch, tmp_path) is True
    assert "because its inputs were not recorded" in capsys.readouterr().out


def test_rebuild_0_rebuilds_when_an_included_file_changes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    header = tmp_path / "rtl" / "defs.svh"
    header.parent.mkdir()
    header.write_text("`define WIDTH 4\n")
    (tmp_path / "rtl" / "top.sv").write_text('`include "defs.svh"\nmodule top; endmodule\n')
    sources = tmp_path / "sources.vf"
    sources.write_text("+incdir+${PROJECT_ROOT}/rtl\n${PROJECT_ROOT}/rtl/top.sv\n")
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("SV_SOURCES_FILE", str(sources))
    assert rebuilds(monkeypatch, tmp_path) is True
    assert rebuilds(monkeypatch, tmp_path) is False
    header.write_text("`define WIDTH 8\n")
    capsys.readouterr()
    assert rebuilds(monkeypatch, tmp_path) is True
    assert "because its input files changed" in capsys.readouterr().out


def test_previous_run_outputs_are_deleted_before_the_build(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build_dir = tmp_path / "build" / "top" / "verilator" / "width4" / "normal"
    stale = [build_dir / "coverage.dat", build_dir / "coverage_html" / "index.html"]
    for output in stale:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.touch()
    seen_at_build: list[bool] = []
    simulator = MagicMock()
    simulator.log = logging.getLogger("flow-test-stale-outputs")

    def record_outputs(**kwargs: object) -> None:
        del kwargs
        seen_at_build.extend(output.exists() for output in stale)

    simulator.build.side_effect = record_outputs
    monkeypatch.setenv("SIM", "verilator")
    monkeypatch.setenv("BUILD_DIR", str(tmp_path / "build"))
    with (
        patch("flow.runner.get_runner", return_value=simulator),
        patch("flow.simulators.require_tool_version"),
    ):
        build_and_test("test_top", config="width4", parameters={"WIDTH": 4})
    assert seen_at_build == [False, False]


def test_a_run_without_the_makefile_sets_project_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    roots: list[str | None] = []
    simulator = MagicMock()
    simulator.log = logging.getLogger("flow-test-project-root")

    def record_root(**kwargs: object) -> None:
        del kwargs
        roots.append(os.environ.get("PROJECT_ROOT"))

    simulator.build.side_effect = record_root
    monkeypatch.setenv("PROJECT_ROOT", "")
    monkeypatch.delenv("PROJECT_ROOT")
    monkeypatch.setenv("SIM", "verilator")
    monkeypatch.setenv("BUILD_DIR", str(tmp_path / "build"))
    with (
        patch("flow.runner.get_runner", return_value=simulator),
        patch("flow.simulators.require_tool_version"),
    ):
        build_and_test("test_top", config="width4", parameters={"WIDTH": 4})
    assert roots == [str(PROJECT_DIR)]
